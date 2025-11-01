CREATE EXTENSION IF NOT EXISTS vector;


CREATE TYPE document_type AS ENUM ('pdf', 'docx');
CREATE TYPE document_status AS ENUM ('pending', 'done', 'failed');

CREATE TABLE document (
    id SERIAL PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL,
    type document_type NOT NULL,
    status document_status NOT NULL,
    path VARCHAR(255),
    created_by BIGINT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_by BIGINT,
    updated_at TIMESTAMP,
    deleted_by BIGINT,
    deleted_at TIMESTAMP
);

CREATE TABLE fragment (
    id SERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL,
    vector VECTOR NOT NULL,
    content TEXT NOT NULL,
    fragment_index INT NOT NULL,
    embedding_model VARCHAR(255) NOT NULL,
    chunk_size INT NOT NULL,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_by BIGINT,
    updated_at TIMESTAMP,
    deleted_by BIGINT,
    deleted_at TIMESTAMP,
    CONSTRAINT fk_fragment_document_id FOREIGN KEY (document_id) REFERENCES "document"(id)
);

CREATE TYPE notification_type AS ENUM ('system', 'admin');

CREATE TABLE notification (
    id SERIAL PRIMARY KEY,
    message VARCHAR(255) NOT NULL,
    type notification_type NOT NULL,
    read_date TIMESTAMP,
    receiver_id BIGINT NOT NULL,
    created_by BIGINT,
    created_at TIMESTAMP NOT NULL,
    deleted_by BIGINT,
    deleted_at TIMESTAMP
);

CREATE TABLE individual_chat (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    purpose VARCHAR(255),
    created_by BIGINT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_by BIGINT,
    updated_at TIMESTAMP,
    deleted_by BIGINT,
    deleted_at TIMESTAMP
);

CREATE TABLE document_in_individual_chat (
    id SERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL,
    individual_chat_id BIGINT NOT NULL,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    deleted_by BIGINT,
    deleted_at TIMESTAMP,
    CONSTRAINT fk_document_in_individual_chat_document_id FOREIGN KEY (document_id) REFERENCES "document"(id),
    CONSTRAINT fk_document_in_individual_chat_individual_chat_id FOREIGN KEY (individual_chat_id) REFERENCES "individual_chat"(id)
);

CREATE TYPE individual_chat_message_sender_type AS ENUM ('system', 'user');

CREATE TABLE individual_chat_message (
    id SERIAL PRIMARY KEY,
    individual_chat_id BIGINT NOT NULL,
    message TEXT NOT NULL,
    sender_type individual_chat_message_sender_type NOT NULL,
    created_by BIGINT,
    created_at TIMESTAMP NOT NULL,
    deleted_by BIGINT,
    deleted_at TIMESTAMP,
    CONSTRAINT fk_individual_chat_message_individual_chat_id FOREIGN KEY (individual_chat_id) REFERENCES "individual_chat"(id)
);

CREATE TABLE group_chat (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    purpose VARCHAR(255),
    created_by BIGINT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_by BIGINT,
    updated_at TIMESTAMP,
    deleted_by BIGINT,
    deleted_at TIMESTAMP
);

CREATE TABLE document_in_group_chat (
    id SERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL,
    group_chat_id BIGINT NOT NULL,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    deleted_by BIGINT,
    deleted_at TIMESTAMP,
    CONSTRAINT fk_document_in_group_chat_document_id FOREIGN KEY (document_id) REFERENCES "document"(id),
    CONSTRAINT fk_document_in_group_chat_group_chat_id FOREIGN KEY (group_chat_id) REFERENCES "group_chat"(id)
);

CREATE TYPE group_chat_message_sender_type AS ENUM ('system', 'user');

CREATE TABLE group_chat_message (
    id SERIAL PRIMARY KEY,
    group_chat_id BIGINT NOT NULL,
    message TEXT NOT NULL,
    sender_type group_chat_message_sender_type NOT NULL,
    created_by BIGINT,
    created_at TIMESTAMP NOT NULL,
    deleted_by BIGINT,
    deleted_at TIMESTAMP,
    CONSTRAINT fk_group_chat_message_group_chat_id FOREIGN KEY (group_chat_id) REFERENCES "group_chat"(id)
);

CREATE TYPE group_chat_membership_status AS ENUM ('active', 'inactive', 'pending');

CREATE TABLE group_chat_membership (
    id SERIAL PRIMARY KEY,
    member_id BIGINT NOT NULL,
    group_chat_id BIGINT NOT NULL,
    status group_chat_membership_status NOT NULL,
    joined_at TIMESTAMP,
    left_at TIMESTAMP,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_by BIGINT,
    updated_at TIMESTAMP,
    deleted_by BIGINT,
    deleted_at TIMESTAMP,
    CONSTRAINT fk_group_chat_membership_group_chat_id FOREIGN KEY (group_chat_id) REFERENCES "group_chat"(id),
    CONSTRAINT group_chat_membership_index_0 UNIQUE (member_id, group_chat_id)
);

CREATE TABLE document_collection (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_by BIGINT,
    updated_at TIMESTAMP,
    deleted_by BIGINT,
    deleted_at TIMESTAMP
);

CREATE TABLE document_in_document_collection (
    id SERIAL PRIMARY KEY,
    document_collection_id BIGINT NOT NULL,
    document_id BIGINT NOT NULL,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    deleted_by BIGINT,
    deleted_at TIMESTAMP,
    CONSTRAINT fk_document_in_document_collection_document_collection_id FOREIGN KEY (document_collection_id) REFERENCES "document_collection"(id),
    CONSTRAINT fk_document_in_document_collection_document_id FOREIGN KEY (document_id) REFERENCES "document"(id),
    CONSTRAINT document_in_document_collection_index_0 UNIQUE (document_collection_id, document_id)
);

CREATE TABLE user_in_document_collection (
    id SERIAL PRIMARY KEY,
    document_collection_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    created_by BIGINT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    deleted_by BIGINT,
    deleted_at TIMESTAMP,
    CONSTRAINT fk_user_in_document_collection_document_collection_id FOREIGN KEY (document_collection_id) REFERENCES "document_collection"(id),
    CONSTRAINT duser_in_document_collection_index_0 UNIQUE (document_collection_id, user_id)
);
