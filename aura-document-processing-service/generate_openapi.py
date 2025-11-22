import json

from app.main import app


with open("docs/openapi.json", "w") as f:
    json.dump(app.openapi(), f, indent=2)


print("openapi.json generado correctamente.")
