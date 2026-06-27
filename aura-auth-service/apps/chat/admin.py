"""El admin de chats ahora vive en accounts/admin_parts/chat_management_admin.py
como vistas propias; aca ya no se registra ningun ModelAdmin.

Los modelos de chat/models.py se mantienen porque el listado los usa como
respaldo y el dashboard lee ArtifactMessage.
"""
