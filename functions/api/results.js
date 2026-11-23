// API de coleta: recebe SOMENTE valores derivados da senha (calculados no navegador) e grava no D1.
// Não registra IP, e-mail, login, cookies ou qualquer outro identificador.

const MAX_BODY_BYTES = 1024;

const ALLOWED_KEYS = [
  "score",
  "guesses_log10",
  "length",
  "has_lower",
  "has_upper",
  "has_digit",
  "has_symbol",
  "patterns",
];

const BOOLEAN_KEYS = ["has_lower", "has_upper", "has_digit", "has_symbol"];

const ALLOWED_PATTERNS = ["dictionary", "sequence", "repeat", "keyboard", "date", "none"];

function jsonResponse(status, body) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}

// Devolve uma mensagem de erro, ou null se o payload for válido
function validate(payload) {
  if (payload === null || typeof payload !== "object" || Array.isArray(payload)) {
    return "payload deve ser um objeto";
  }

  const keys = Object.keys(payload);
  if (keys.length !== ALLOWED_KEYS.length || !ALLOWED_KEYS.every(key => keys.includes(key))) {
    return "campos inválidos";
  }

  const { score, guesses_log10, length, patterns } = payload;

  if (!Number.isInteger(score) || score < 0 || score > 4) return "score inválido";
  if (typeof guesses_log10 !== "number" || !Number.isFinite(guesses_log10) || guesses_log10 < 0 || guesses_log10 > 200) {
    return "guesses_log10 inválido";
  }
  if (!Number.isInteger(length) || length < 1 || length > 128) return "length inválido";

  for (const key of BOOLEAN_KEYS) {
    if (typeof payload[key] !== "boolean") return key + " inválido";
  }
  if (!payload.has_lower && !payload.has_upper && !payload.has_digit && !payload.has_symbol) {
    return "nenhuma classe de caracteres";
  }

  if (!Array.isArray(patterns) || patterns.length < 1 || patterns.length > ALLOWED_PATTERNS.length) {
    return "patterns inválido";
  }
  if (!patterns.every(pattern => typeof pattern === "string" && ALLOWED_PATTERNS.includes(pattern))) {
    return "pattern desconhecido";
  }
  if (new Set(patterns).size !== patterns.length) return "patterns repetidos";
  if (patterns.includes("none") && patterns.length > 1) return "'none' não combina com outros padrões";

  return null;
}

export async function onRequestPost({ request, env }) {
  const contentType = request.headers.get("Content-Type") || "";
  if (!contentType.toLowerCase().startsWith("application/json")) {
    return jsonResponse(415, { error: "use application/json" });
  }

  const rawBody = await request.text();
  if (new TextEncoder().encode(rawBody).length > MAX_BODY_BYTES) {
    return jsonResponse(413, { error: "payload muito grande" });
  }

  let payload;
  try {
    payload = JSON.parse(rawBody);
  } catch {
    return jsonResponse(400, { error: "JSON inválido" });
  }

  const error = validate(payload);
  if (error) return jsonResponse(400, { error });

  const has = pattern => (payload.patterns.includes(pattern) ? 1 : 0);

  await env.DB.prepare(
    `INSERT INTO responses (
       score, guesses_log10, length,
       has_lower, has_upper, has_digit, has_symbol,
       pattern_dictionary, pattern_sequence, pattern_repeat, pattern_keyboard, pattern_date, pattern_none
     ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`
  ).bind(
    payload.score,
    payload.guesses_log10,
    payload.length,
    payload.has_lower ? 1 : 0,
    payload.has_upper ? 1 : 0,
    payload.has_digit ? 1 : 0,
    payload.has_symbol ? 1 : 0,
    has("dictionary"),
    has("sequence"),
    has("repeat"),
    has("keyboard"),
    has("date"),
    has("none"),
  ).run();

  return jsonResponse(201, { ok: true });
}

// Qualquer outro método (GET, PUT, DELETE...) é recusado: os dados não podem ser lidos pela API.
export async function onRequest() {
  return jsonResponse(405, { error: "método não permitido" });
}
