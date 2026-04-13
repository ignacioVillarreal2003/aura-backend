from drf_spectacular.extensions import OpenApiAuthenticationExtension


class ServiceAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "core.authentication.backends.ServiceAuthentication"
    name = "bearerAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "User token validated by the external auth service.",
        }
