-- Extensiones que TODOSCARE necesita (también las crea la migración inicial,
-- pero dejarlas aquí garantiza que existan aunque el rol de la app no tenga
-- privilegio para CREATE EXTENSION en algún Postgres gestionado).
--   pgcrypto   -> gen_random_uuid()
--   btree_gist -> opclass "=" en el índice GiST anti doble-reserva de la agenda
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS btree_gist;
