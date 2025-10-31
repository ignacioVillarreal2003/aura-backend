CREATE EXTENSION IF NOT EXISTS vector;

CREATE TYPE document_type AS ENUM ('pdf', 'docx', 'txt');
CREATE TYPE document_status AS ENUM ('pending', 'published');
CREATE TYPE embedding_status AS ENUM ('pending', 'done', 'failed');

CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    type document_type NOT NULL,
    status document_status DEFAULT 'pending' NOT NULL,
    path VARCHAR(255),
    size INTEGER,
    created_by BIGINT NOT NULL,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_by BIGINT,
    updated_date TIMESTAMP,
    deleted_by BIGINT,
    deleted_date TIMESTAMP,
    embedding_status embedding_status DEFAULT 'pending',
    vector_count INTEGER,
    hash VARCHAR(255)
);
