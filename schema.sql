-- Tabela das respostas. Só valores derivados: nenhuma senha, IP, e-mail ou login.
CREATE TABLE IF NOT EXISTS responses (
  id                 INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at         TEXT    NOT NULL DEFAULT (datetime('now')),
  score              INTEGER NOT NULL CHECK (score BETWEEN 0 AND 4),
  guesses_log10      REAL    NOT NULL CHECK (guesses_log10 >= 0 AND guesses_log10 <= 200),
  length             INTEGER NOT NULL CHECK (length BETWEEN 1 AND 128),
  has_lower          INTEGER NOT NULL CHECK (has_lower IN (0, 1)),
  has_upper          INTEGER NOT NULL CHECK (has_upper IN (0, 1)),
  has_digit          INTEGER NOT NULL CHECK (has_digit IN (0, 1)),
  has_symbol         INTEGER NOT NULL CHECK (has_symbol IN (0, 1)),
  pattern_dictionary INTEGER NOT NULL CHECK (pattern_dictionary IN (0, 1)),
  pattern_sequence   INTEGER NOT NULL CHECK (pattern_sequence IN (0, 1)),
  pattern_repeat     INTEGER NOT NULL CHECK (pattern_repeat IN (0, 1)),
  pattern_keyboard   INTEGER NOT NULL CHECK (pattern_keyboard IN (0, 1)),
  pattern_date       INTEGER NOT NULL CHECK (pattern_date IN (0, 1)),
  pattern_none       INTEGER NOT NULL CHECK (pattern_none IN (0, 1))
);
