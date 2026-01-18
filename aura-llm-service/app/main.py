import asyncio
import logging
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.controllers import router
from app.configuration.dependencies import startup_dependencies, shutdown_dependencies
from app.configuration.logging_configuration import configure_logging
from app.configuration.environment_variables import environment_variables

configure_logging(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=" * 60)
    logger.info("Starting FastAPI Application")
    logger.info("=" * 60)

    try:
        await startup_dependencies()
        logger.info("Application started successfully")

    except Exception:
        logger.critical("Failed to start application")
        raise

    yield

    logger.info("=" * 60)
    logger.info("Shutting down FastAPI Application")
    logger.info("=" * 60)

    try:
        await shutdown_dependencies()
        logger.info("Application shut down successfully")

    except Exception:
        logger.error("Error during application shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title=environment_variables.app_name,
        version=environment_variables.app_version,
        description="Agent-based document question answering",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json"
    )

    configure_cors(app)
    add_middleware(app)
    include_routers(app)
    add_exception_handlers(app)

    logger.info("FastAPI application configured")

    return app


def configure_cors(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=environment_variables.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    logger.debug("CORS configured")


def add_middleware(app: FastAPI) -> None:
    @app.middleware("http_client")
    async def log_requests(request: Request,
                           call_next):
        logger.info(f"Request: {request.method} {request.url.path}")

        response = await call_next(request)

        logger.info(f"Response: {response.status_code}")

        return response

    logger.debug("Middleware added")


def include_routers(app: FastAPI) -> None:
    app.include_router(
        router,
        prefix="/api"
    )

    @app.get("/health", tags=["Health"])
    async def health_check():
        return {
            "status": "healthy",
            "app": environment_variables.app_name,
            "version": environment_variables.app_version
        }

    logger.debug("Routers included")


def add_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request,
                                     exc: StarletteHTTPException):
        logger.warning(
            f"HTTP exception: {exc.status_code}",
            extra={
                "status_code": exc.status_code,
                "detail": exc.detail,
                "path": request.url.path
            }
        )

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "HTTPException",
                "message": exc.detail,
                "status_code": exc.status_code
            }
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request,
                                           exc: RequestValidationError):
        logger.warning(
            "Validation error",
            extra={
                "path": request.url.path,
                "errors": exc.errors()
            }
        )

        return JSONResponse(
            status_code=422,
            content={
                "error": "ValidationError",
                "message": "Request validation failed",
                "details": exc.errors()
            }
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request,
                                        exc: Exception):
        logger.exception(
            "Unexpected error",
            extra={
                "path": request.url.path,
                "error_type": type(exc).__name__
            }
        )

        return JSONResponse(
            status_code=500,
            content={
                "error": "InternalServerError",
                "message": "An unexpected error occurred"
            }
        )

    logger.debug("Exception handlers added")


app = create_app()

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=environment_variables.app_host,
        port=environment_variables.app_port,
        reload=environment_variables.app_reload,
        log_level=environment_variables.log_level.lower()
    )




class MockExternalApiRequest(BaseModel):
    document_id: int

@app.post("/mock/external-api")
async def mock_external_api(
    request: MockExternalApiRequest
):
    await asyncio.sleep(0.8)

    return {
        "context_fragments": [
            "En una mañana gris junto al puerto, un perro curioso llamado Bruno olfateaba todo lo que encontraba. Nunca había visto el mar tan quieto, ni había imaginado que algo tan grande pudiera esconderse bajo esa superficie tranquila. Las gaviotas sobrevolaban los barcos, y el olor a sal mezclado con pescado fresco llenaba el aire, haciendo que sus orejas se movieran al compás del viento. Bruno caminaba por las tablas del muelle, inspeccionando cada cajón, cada cuerda, cada sombra que proyectaban las viejas grúas de madera y hierro. Incluso los barcos más pequeños parecían gigantes desde su perspectiva canina, y la sensación de aventura lo llenaba de emoción y un poco de nerviosismo.",
            "De pronto, una ballena joven asomó la cabeza cerca del muelle, expulsando un chorro de agua que asustó a todos. Bruno, más valiente que sensato, saltó al borde y, creyendo que era un juego, le mordió suavemente la aleta. El impacto del contacto hizo que el agua se agitara violentamente, y algunas gaviotas huyeron con chillidos mientras las olas rompían contra los muros del puerto. La ballena giró lentamente, mirándolo con sus ojos grandes y expresivos, transmitiendo una mezcla de curiosidad y sorpresa. Bruno, sin entender del todo la magnitud de su acción, movía la cola con entusiasmo, esperando que su nuevo amigo siguiera jugando. Los pescadores, que habían presenciado la escena desde la cubierta de sus barcos, sonrieron y se preguntaron cuánto tiempo tardaría el perro en darse cuenta de la verdadera naturaleza de su interlocutor.",
            "La ballena, sorprendida pero paciente, se alejó lentamente mar adentro, mientras Bruno ladraba orgulloso. Desde ese día, el perro del puerto aprendió que no todo lo enorme es peligroso, y que incluso un mordisco puede convertirse en una historia para recordar. Durante semanas, Bruno regresaba al mismo lugar, esperando ver de nuevo a la ballena, y aunque nunca volvió exactamente igual, cada vez que el agua se movía de manera extraña, su corazón latía con la misma emoción de aquel primer encuentro. Los habitantes del puerto empezaron a contar la historia del valiente perro que mordió a la ballena, convirtiendo a Bruno en una pequeña leyenda local. Con cada amanecer, el perro exploraba cada rincón del puerto, persiguiendo olas, observando barcos y aprendiendo a medir la magnitud del mundo, siempre con la memoria de aquel día único grabada en su espíritu. Incluso la ballena parecía reconocer al pequeño intrépido amigo cada vez que emergía cerca del muelle, y aunque sus encuentros eran esporádicos, mantenían un vínculo silencioso lleno de respeto y admiración mutua. Los niños del pueblo, inspirados por la historia, comenzaron a visitar el muelle con cuidado, trayendo juguetes para que Bruno jugara y compartiendo con él su curiosidad y alegría. Con cada visita, el puerto se llenaba de risas, olas y ladridos, y la leyenda del perro y la ballena crecía, recordándole a todos que la valentía y la amistad pueden encontrarse en los lugares más inesperados."
            "Con el paso de los días, Bruno se volvió más aventurero. Ya no se conformaba con olfatear los barcos y cajas del muelle; empezaba a explorar los rincones del puerto que antes le daban miedo: los almacenes abandonados, los pasillos estrechos entre las grúas y hasta los embarcaderos casi hundidos. Cada descubrimiento lo hacía sentir como un verdadero explorador canino, y su curiosidad no tenía límites. A menudo, al regresar de sus excursiones, se tumbaba bajo la sombra de un viejo faro, observando cómo el sol pintaba de oro la superficie del agua, recordando aquel primer encuentro con la ballena y soñando con nuevas aventuras.",
            "Una tarde, mientras el viento traía el aroma de algas y sal marina, Bruno percibió un sonido diferente: un canto suave, profundo, que parecía provenir del centro del puerto. Se acercó sigilosamente, con las patas rozando la madera húmeda, y vio cómo la ballena emergía parcialmente, mostrando su enorme cuerpo con gracia y calma. Esta vez no se trataba de un encuentro accidental: la ballena parecía invitarlo a seguirla. Bruno, aunque sabía que no podía nadar tan lejos, corrió a lo largo del muelle y ladró con entusiasmo, como diciendo '¡Aquí estoy!'. Los pescadores miraban asombrados, algunos con preocupación, otros con una sonrisa de incredulidad ante la audacia del perro.",
            "Bruno comenzó a pasar más tiempo junto al agua, aprendiendo a interpretar los movimientos de las olas y el comportamiento de los barcos. Descubrió que ciertos momentos del día eran ideales para observar a la ballena, especialmente al amanecer y al atardecer, cuando el mar parecía calmo y las sombras se alargaban, creando un escenario perfecto para aventuras y juegos. Incluso empezó a familiarizarse con otros animales del puerto: gatos curiosos, gaviotas insistentes y peces que saltaban cerca de la superficie, como saludándolo. Cada interacción lo volvía más astuto, y su confianza crecía con cada jornada.",
            "Un día, mientras Bruno exploraba un almacén antiguo junto al muelle, encontró un objeto brillante entre las tablas del suelo: era un viejo medallón, corroído por la sal y el tiempo, con una inscripción apenas legible. La curiosidad lo llevó a traerlo al muelle y mostrarlo a la ballena, como si pudiera comunicarse a través del objeto. La ballena se acercó, tocando suavemente el medallón con su aleta, y el perro sintió una especie de conexión más profunda, como si aquel hallazgo simbolizara el vínculo que habían creado. Los pescadores, al verlo, comenzaron a inventar historias sobre tesoros escondidos y aventuras marinas, y la leyenda del perro y la ballena se mezclaba con cuentos de piratas y secretos antiguos.",
            "A medida que pasaba el tiempo, Bruno empezó a notar cambios en el comportamiento de la ballena: ya no solo emergía cerca del muelle, sino que realizaba movimientos elegantes alrededor de barcos y boyas, como si enseñara al perro pequeños juegos acuáticos. Bruno intentaba imitarlos desde la orilla, corriendo de un lado a otro, saltando sobre las tablas y ladrando con entusiasmo. Los niños del pueblo, inspirados por la relación, se unieron a las aventuras, trayendo pelotas y flotadores que Bruno lanzaba al agua, esperando que la ballena jugara con ellos. Cada día era un espectáculo de amistad entre especies, con risas humanas y ladridos mezclados con los suaves chorros de agua que la ballena expulsaba.",
            "Durante el invierno, cuando el viento soplaba más fuerte y las olas eran más altas, Bruno aprendió a ser paciente. Ya no saltaba al primer movimiento del agua; observaba, calculaba y reaccionaba con cuidado. La ballena, por su parte, parecía comprender que el perro debía adaptarse a las condiciones difíciles, y sus encuentros se volvieron más sutiles, casi rituales. Bruno empezó a reconocer patrones en el comportamiento del mar: cuándo las mareas subían, cuándo los barcos se movían, e incluso cuándo las gaviotas cambiaban de rumbo. Todo esto le dio una sensación de control y entendimiento del mundo marino que antes le resultaba desconocido.",
            "Una tarde, mientras el cielo se teñía de colores rosados y naranjas, Bruno vio algo inesperado: otra ballena joven se acercaba, acompañando a su amiga del puerto. Al principio se mostró receloso, pero pronto entendió que no había amenaza. La nueva ballena se movía con curiosidad, observando al perro con los mismos ojos que su amiga, y Bruno decidió que debía aprender a interactuar con ella también. Saltó y ladró suavemente, y ambas ballenas respondieron con chorros de agua y movimientos elegantes, como si celebraran la llegada del pequeño intrépido amigo que tanto les había enseñado sobre la paciencia y la amistad.",
            "Con la llegada de la primavera, Bruno se volvió casi una celebridad en el puerto. Los turistas y habitantes lo reconocían, señalándolo con sonrisas, y muchos llevaban pequeños regalos: huesos, pelotas y golosinas. Pero más allá de los premios, lo que Bruno valoraba era la compañía de la ballena y la sensación de explorar un mundo que parecía infinito. Cada amanecer traía nuevas aventuras: descubrir cuevas escondidas, seguir barcos que cruzaban el horizonte y escuchar los cantos misteriosos del océano. Cada fragmento de experiencia se sumaba a la gran historia que unía al perro, la ballena y el puerto, convirtiéndose en recuerdos imborrables que perdurarían para siempre.",
            "Incluso los pescadores comenzaron a colaborar con Bruno: algunos arrojaban redes de manera segura para permitir que el perro saltara entre ellas, mientras otros narraban historias antiguas del puerto y de criaturas marinas que, según decían, compartían secretos con quienes demostraban coraje y curiosidad. Bruno aprendió a escuchar atentamente, a interpretar las palabras humanas y los sonidos del mar, y cada día parecía comprender un poco más el lenguaje universal de la aventura, la paciencia y la amistad. La ballena, siempre presente, seguía siendo su guía silenciosa, recordándole que la grandeza no siempre se mide por el tamaño, sino por la bondad y el respeto entre seres que se encuentran por casualidad en el vasto mundo."
        ]

    }

