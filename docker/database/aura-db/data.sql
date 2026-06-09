INSERT INTO classification_level (name, rank)
VALUES
    ('PUBLIC', 1),
    ('INTERNAL', 2),
    ('CONFIDENTIAL', 3),
    ('RESTRICTED', 4);

INSERT INTO compartment (name, description)
VALUES
    ('Program-Alpha', 'Necesidad de conocer programa Alpha (manual operativo general).'),
    ('Program-Bravo', 'Ámbito Bravo (información táctica de unidad).'),
    ('Program-Charlie', 'Integración sistemas Charlie (solo personal asignado).');
