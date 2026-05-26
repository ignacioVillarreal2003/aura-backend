from drf_spectacular.extensions import OpenApiAuthenticationExtension


class ServiceAuthenticationExtension(OpenApiAuthenticationExtension):
    target_class = "core.authentication.service_authentication.ServiceAuthentication"
    name = "BearerAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": (
                "JWT emitido por el servicio de autenticación. "
                "El middleware lo valida antes de llegar al view y popula `request.user`."
            ),
        }
