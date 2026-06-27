import logging
import re
from typing import Optional
from django.utils import timezone
from asgiref.sync import sync_to_async

from core.authentication.authenticated_user import AuthenticatedUser
from core.authorization.access import AccessControl
from core.authorization import permissions as perms
from core.clients.exceptions import HttpClientException
from core.clients.llm_client import llm_client
from apps.chat.exceptions import ChatNotFoundException
from apps.chat.repositories.chat_repository import chat_repository
from apps.artifact.models import Artifact
from django.db import transaction
from apps.artifact.broadcasting import broadcast_artifact_created, broadcast_artifact_progress
from apps.artifact.services.artifact_service import create_artifact_for_content
from apps.artifact.services.artifact_crud_service import ArtifactCrudService
from apps.artifact.llm_context import build_chat_history
from apps.artifact_report.exceptions import LLMServiceException, ReportAccessDeniedException, ReportNotFoundException
from apps.artifact_report.models import ArtifactReport
from apps.artifact_report.repositories.report_repository import report_repository

logger = logging.getLogger(__name__)

_DOCUMENTS_ONLY_INSTRUCTION = "Generá el informe a partir del o los documentos adjuntos."

_AUTO_TITLE_MAX_CHARS = 80
_DESCRIPTION_MAX_CHARS = 240

# Encabezado de sección numerado, p.ej. "2. MISIÓN" o "5. CONCLUSIONES Y ANÁLISIS".
_SECTION_RE = re.compile(r"^\s*\d+\.\s*(.+?)\s*:?\s*$")
# Marcadores entre corchetes que el modelo puede dejar: [SIN DATOS], [NIVEL], etc.
_PLACEHOLDER_RE = re.compile(r"\[[^\]]*\]")
# Rótulo de plantilla al inicio de la MISIÓN (p.ej. "QUIÉN – QUÉ – CUÁNDO – DÓNDE – POR QUÉ:").
# Una corrida inicial en MAYÚSCULAS con separadores que termina en ":" es siempre una etiqueta.
_LABEL_PREFIX_RE = re.compile(r"^[A-ZÁÉÍÓÚÑ¿?()/0-9 .–—-]{6,}:\s*")
# Sección que mejor resume el informe, según el tipo (MISIÓN para SITREP/OPORD,
# CONCLUSIONES para INTSUM).
_SUMMARY_SECTION_KEYWORDS = ("MISIÓN", "MISION", "CONCLUSIONES", "RESUMEN")
_UNIDAD_PREFIXES = ("UNIDAD:", "ORGANIZACIÓN DE TAREA:", "ORGANIZACION DE TAREA:")


def _clean_inline(text: str) -> str:
    text = _PLACEHOLDER_RE.sub("", text)
    text = text.replace("*", "").replace("#", "").replace("`", "")
    return re.sub(r"\s+", " ", text).strip(" -–—:•").strip()


def _extract_section_body(content: str, keywords: tuple[str, ...]) -> str:
    lines = content.splitlines()
    start: Optional[int] = None
    for i, line in enumerate(lines):
        match = _SECTION_RE.match(line)
        if match and any(kw in match.group(1).upper() for kw in keywords):
            start = i + 1
            break
    if start is None:
        return ""
    body: list[str] = []
    for line in lines[start:]:
        if _SECTION_RE.match(line):
            break
        body.append(line)
    return "\n".join(body)


def _summary_text(content: str) -> str:
    body = _extract_section_body(content, _SUMMARY_SECTION_KEYWORDS)
    summary = _clean_inline(" ".join(ln for ln in body.splitlines() if _clean_inline(ln)))
    summary = _LABEL_PREFIX_RE.sub("", summary).strip()
    if summary:
        return summary
    # Fallback: primera línea sustantiva que no sea un metadato del encabezado.
    for line in content.splitlines():
        cleaned = _clean_inline(line)
        head = line.strip().split(" ", 1)[0]
        if len(cleaned) >= 24 and not head.endswith(":"):
            return cleaned
    return ""


def _extract_unidad(content: str) -> str:
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith(_UNIDAD_PREFIXES):
            value = _clean_inline(stripped.split(":", 1)[1])
            if value:
                return value
    return ""


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _derive_title_and_description(report_type: str, content: str) -> tuple[str, str]:
    summary = _summary_text(content)
    if summary:
        sentence = re.split(r"(?<=[.;])\s", summary, maxsplit=1)[0].strip()
        title = sentence if 0 < len(sentence) <= _AUTO_TITLE_MAX_CHARS else summary
        return _truncate(title, _AUTO_TITLE_MAX_CHARS), _truncate(summary, _DESCRIPTION_MAX_CHARS)

    unidad = _extract_unidad(content)
    if unidad:
        return _truncate(unidad, _AUTO_TITLE_MAX_CHARS), ""

    ts = timezone.now().strftime("%d/%m/%Y %H:%M")
    return f"Informe {report_type} — {ts}", ""


@transaction.atomic
def _persist_generated_report(
        *,
        user_id: int,
        report_type: str,
        title: str,
        description: str,
        retrieve_context: bool | None,
        process_documents: bool | None,
        document_ids: list[int],
        source_chat_id: int,
        content: str,
        query: str = "",
        fragments=None,
) -> tuple:
    artifact = create_artifact_for_content(
        user_id=user_id,
        artifact_type=Artifact.Type.REPORT,
        retrieve_context=retrieve_context,
        process_documents=process_documents,
        document_ids=document_ids,
        source_chat_id=source_chat_id,
        fragments=fragments,
    )
    report = report_repository.create(
        user_id=user_id,
        type=report_type,
        content=content,
        artifact_id=artifact.id,
        title=title,
        description=description,
        query=query,
    )
    return artifact, report


class ReportService(ArtifactCrudService):
    repository = report_repository
    not_found_exc = ReportNotFoundException
    access_denied_exc = ReportAccessDeniedException
    log_model = "ArtifactReport"
    log_id_key = "report_id"
    perm_list = perms.LIST_REPORTS
    perm_manage = perms.MANAGE_REPORTS
    perm_get = perms.GET_REPORT
    perm_export = perms.EXPORT_REPORT
    perm_manage_export = perms.MANAGE_EXPORT_REPORT
    perm_delete = perms.DELETE_REPORT
    logger = logger

    def list_reports(
            self,
            user: AuthenticatedUser,
            chat_id: int,
            report_type: Optional[str] = None,
    ):
        return self._list_by_chat(user, chat_id, report_type=report_type)

    def list_all_reports(
            self,
            user: AuthenticatedUser,
            report_type: Optional[str] = None,
    ):
        return self._list_all(user, report_type=report_type)

    def get_report(self, user: AuthenticatedUser, report_id: int) -> ArtifactReport:
        return self._get(user, report_id)

    def get_own_report(self, user: AuthenticatedUser, report_id: int) -> ArtifactReport:
        return self._get_own(user, report_id)

    def get_report_admin_export(self, user: AuthenticatedUser, report_id: int) -> ArtifactReport:
        return self._get_admin_export(user, report_id)

    def delete_report(self, user: AuthenticatedUser, report_id: int) -> None:
        self._delete(user, report_id)

    async def generate_report(
            self,
            user: AuthenticatedUser,
            report_type: str,
            message: str,
            chat_id: int,
            retrieve_context: bool | None = None,
            process_documents: bool | None = None,
            document_ids: list[int] | None = None,
    ) -> tuple[ArtifactReport, list[dict], list[dict]]:
        AccessControl.require_permissions(user, frozenset({perms.LLM_REPORT_GENERATE}))

        chat = await sync_to_async(chat_repository.get_by_id)(chat_id)
        if chat is None:
            raise ChatNotFoundException()
        system_prompt = chat.system_prompt if chat else None
        response_style = chat.response_style if chat else None
        history = await sync_to_async(build_chat_history)(chat_id)

        human_text = message.strip() if message else _DOCUMENTS_ONLY_INSTRUCTION
        messages = history + [{"role": "human", "content": human_text}]
        result_data: dict | None = None
        try:
            async for event in llm_client.generate_report_stream_events(
                    messages=messages,
                    report_type=report_type,
                    user=user,
                    chat_id=chat_id,
                    system_prompt=system_prompt,
                    response_style=response_style,
                    retrieve_context=retrieve_context,
                    process_documents=process_documents,
                    document_ids=document_ids,
            ):
                et = event.get("type")
                if et == "progress":
                    await broadcast_artifact_progress(chat_id, str(event.get("step", "")),
                                                      str(event.get("message", "")))
                elif et == "complete":
                    result_data = event.get("result") or {}
                elif et == "error":
                    logger.error(
                        "LLM report stream error: %s", event.get("message", ""),
                        extra={"user_id": user.id, "code": event.get("code")},
                    )
                    raise LLMServiceException()
        except HttpClientException as e:
            logger.error(
                "LLM report-generate stream failed: %s",
                str(e),
                extra={"user_id": user.id, "report_type": report_type, "status_code": e.status_code},
                exc_info=True,
            )
            raise LLMServiceException() from e

        if result_data is None:
            logger.error("LLM report stream ended without complete event", extra={"user_id": user.id})
            raise LLMServiceException()

        content = str(result_data.get("content", "")).strip()
        rtype = str(result_data.get("report_type", report_type))
        out_messages = result_data.get("messages") or []
        fragments = llm_client.normalize_fragments(result_data.get("fragments"))

        if not content:
            logger.error("LLM returned empty content for report", extra={"user_id": user.id, "report_type": rtype})
            raise LLMServiceException()
        if rtype not in ArtifactReport.Type.values:
            logger.error("LLM returned unknown report type: %s", rtype, extra={"user_id": user.id})
            raise LLMServiceException()

        # El LLM ahora devuelve title/description; si vienen vacíos (fallback de
        # texto plano), los derivamos del contenido como red de seguridad.
        title = _truncate(str(result_data.get("title", "")).strip(), _AUTO_TITLE_MAX_CHARS)
        description = _truncate(str(result_data.get("description", "")).strip(), _DESCRIPTION_MAX_CHARS)
        if not title:
            title, description = _derive_title_and_description(rtype, content)
        artifact, report = await sync_to_async(_persist_generated_report)(
            user_id=user.id,
            report_type=rtype,
            title=title,
            description=description,
            retrieve_context=retrieve_context,
            process_documents=process_documents,
            document_ids=document_ids or [],
            source_chat_id=chat_id,
            content=content,
            query=message,
            fragments=fragments,
        )

        report.artifact = artifact
        logger.info(
            "ArtifactReport generated and saved",
            extra={
                "user_id": user.id,
                "report_id": report.id,
                "type": rtype,
                "source_chat_id": chat_id,
                "artifact_id": artifact.id,
            },
        )
        await broadcast_artifact_created(chat_id, artifact)
        return report, out_messages, fragments


report_service = ReportService()
