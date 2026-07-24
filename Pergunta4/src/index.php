<?php
$phpVersion = phpversion();
$generatedAt = date('d/m/Y H:i:s');

// Testa conexão real com o MariaDB (não quebra a página se a extensão faltar)
$dbHost = getenv('DB_HOST') ?: 'mariadb';
$dbName = getenv('DB_NAME') ?: 'appdb';
$dbUser = getenv('DB_USER') ?: 'appuser';
$dbPass = getenv('DB_PASS') ?: 'apppassword';

$dbStatus = 'indisponível';
$dbDetail = 'Extensão mysqli não instalada na imagem PHP.';
$dbOk = false;

if (function_exists('mysqli_connect')) {
    try {
        $conn = mysqli_connect($dbHost, $dbUser, $dbPass, $dbName);
        $dbOk = true;
        $dbStatus = 'conectado';
        $dbDetail = 'Banco "' . htmlspecialchars($dbName) . '" respondendo em ' . htmlspecialchars($dbHost) . '.';
        mysqli_close($conn);
    } catch (mysqli_sql_exception $e) {
        $dbStatus = 'falha';
        $dbDetail = 'Não foi possível conectar em ' . htmlspecialchars($dbHost) . '.';
    }
}

$services = [
    [
        'name' => 'Nginx',
        'role' => 'proxy reverso',
        'status' => 'ok',
        'detail' => 'Servindo requisições na porta 8080.',
    ],
    [
        'name' => 'PHP-FPM',
        'role' => 'runtime',
        'status' => 'ok',
        'detail' => 'PHP ' . $phpVersion . ' processando este arquivo agora.',
    ],
    [
        'name' => 'MariaDB',
        'role' => 'banco de dados',
        'status' => $dbOk ? 'ok' : ($dbStatus === 'falha' ? 'falha' : 'atenção'),
        'detail' => $dbDetail,
    ],
];

// --- Teste de persistência: grava e lista mensagens na tabela `mensagens` ---
$mensagens = [];
$formError = null;
$formSuccess = null;

if ($dbOk) {
    $conn = null;

    try {
        $conn = mysqli_connect($dbHost, $dbUser, $dbPass, $dbName);

        if ($_SERVER['REQUEST_METHOD'] === 'POST' && !empty(trim($_POST['texto'] ?? ''))) {
            $texto = mysqli_real_escape_string($conn, trim($_POST['texto']));
            mysqli_query($conn, "INSERT INTO mensagens (texto) VALUES ('$texto')");
            $formSuccess = 'Mensagem gravada no banco.';
        }

        $result = mysqli_query($conn, "SELECT id, texto, criado_em FROM mensagens ORDER BY criado_em DESC, id DESC LIMIT 20");
        while ($row = mysqli_fetch_assoc($result)) {
            $mensagens[] = $row;
        }
    } catch (mysqli_sql_exception $e) {
        $formSuccess = null;
        $formError = 'Tabela "mensagens" ainda não existe. Rode "docker compose down -v" e suba de novo para reinicializar o banco com o script sql/init.sql.';
    }

    if ($conn) {
        mysqli_close($conn);
    }
}
?>
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Ambiente no ar · Umbler</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #140f1f;
    --surface: #1e1730;
    --surface-line: #322753;
    --purple: #8b3ffb;
    --purple-soft: #b78bff;
    --ok: #34d399;
    --warn: #fbbf24;
    --fail: #f87171;
    --text: #f3eefe;
    --text-muted: #a89bc9;
  }

  * { box-sizing: border-box; }

  body {
    margin: 0;
    background: var(--bg);
    background-image:
      radial-gradient(circle at 15% 10%, rgba(139, 63, 251, 0.16), transparent 45%),
      radial-gradient(circle at 85% 0%, rgba(139, 63, 251, 0.10), transparent 40%);
    color: var(--text);
    font-family: 'Inter', sans-serif;
    min-height: 100vh;
    padding: 64px 24px 40px;
  }

  .wrap {
    max-width: 780px;
    margin: 0 auto;
  }

  .eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    letter-spacing: 0.14em;
    color: var(--purple-soft);
    text-transform: uppercase;
    border: 1px solid var(--surface-line);
    background: rgba(139, 63, 251, 0.08);
    padding: 6px 12px;
    border-radius: 999px;
  }

  .eyebrow .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--ok);
    box-shadow: 0 0 0 3px rgba(52, 211, 153, 0.2);
  }

  h1 {
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 700;
    font-size: clamp(36px, 6vw, 56px);
    line-height: 1.05;
    margin: 20px 0 12px;
    letter-spacing: -0.01em;
  }

  h1 span {
    color: var(--purple-soft);
  }

  .subhead {
    color: var(--text-muted);
    font-size: 16px;
    line-height: 1.6;
    max-width: 520px;
    margin: 0 0 44px;
  }

  .topology {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    margin-bottom: 40px;
    padding: 20px 8px;
  }

  .node {
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: var(--text-muted);
    text-align: center;
    white-space: nowrap;
  }

  .node-dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: var(--purple);
    margin: 0 auto 8px;
    box-shadow: 0 0 0 4px rgba(139, 63, 251, 0.18);
  }

  .link {
    flex: 1;
    height: 2px;
    background: linear-gradient(90deg, var(--surface-line), var(--purple), var(--surface-line));
    background-size: 200% 100%;
    position: relative;
    top: -14px;
    animation: flow 2.6s linear infinite;
  }

  @keyframes flow {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }

  .cards {
    display: grid;
    gap: 12px;
  }

  .card {
    background: var(--surface);
    border: 1px solid var(--surface-line);
    border-radius: 14px;
    padding: 18px 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 16px;
  }

  .card-left {
    display: flex;
    align-items: center;
    gap: 14px;
  }

  .status-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .status-dot.ok { background: var(--ok); box-shadow: 0 0 0 4px rgba(52, 211, 153, 0.16); }
  .status-dot.atencao { background: var(--warn); box-shadow: 0 0 0 4px rgba(251, 191, 36, 0.16); }
  .status-dot.falha { background: var(--fail); box-shadow: 0 0 0 4px rgba(248, 113, 113, 0.16); }

  .card-name {
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 700;
    font-size: 16px;
  }

  .card-role {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .card-detail {
    font-size: 13px;
    color: var(--text-muted);
    text-align: right;
    max-width: 260px;
  }

  .card-status-label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .card-status-label.ok { color: var(--ok); }
  .card-status-label.atencao { color: var(--warn); }
  .card-status-label.falha { color: var(--fail); }

  footer {
    margin-top: 48px;
    padding-top: 20px;
    border-top: 1px solid var(--surface-line);
    display: flex;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 8px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    color: var(--text-muted);
  }

  @media (max-width: 560px) {
    .card { flex-direction: column; align-items: flex-start; }
    .card-detail { text-align: left; max-width: 100%; }
    .topology { display: none; }
  }

  .section-title {
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 700;
    font-size: 22px;
    margin: 56px 0 6px;
  }

  .section-hint {
    color: var(--text-muted);
    font-size: 14px;
    line-height: 1.6;
    margin: 0 0 20px;
    max-width: 560px;
  }

  .section-hint code {
    font-family: 'JetBrains Mono', monospace;
    background: rgba(139, 63, 251, 0.12);
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 12px;
  }

  form.persist-form {
    display: flex;
    gap: 10px;
    margin-bottom: 16px;
  }

  form.persist-form input[type="text"] {
    flex: 1;
    background: var(--surface);
    border: 1px solid var(--surface-line);
    border-radius: 10px;
    padding: 12px 14px;
    color: var(--text);
    font-family: 'Inter', sans-serif;
    font-size: 14px;
  }

  form.persist-form input[type="text"]:focus {
    outline: none;
    border-color: var(--purple);
  }

  form.persist-form button {
    background: var(--purple);
    color: #fff;
    border: none;
    border-radius: 10px;
    padding: 0 20px;
    font-family: 'Space Grotesk', sans-serif;
    font-weight: 700;
    font-size: 14px;
    cursor: pointer;
    transition: background 0.15s ease;
  }

  form.persist-form button:hover {
    background: #7a2ef0;
  }

  .flash {
    font-family: 'JetBrains Mono', monospace;
    font-size: 12px;
    padding: 10px 14px;
    border-radius: 10px;
    margin-bottom: 16px;
  }

  .flash.success {
    background: rgba(52, 211, 153, 0.1);
    color: var(--ok);
    border: 1px solid rgba(52, 211, 153, 0.25);
  }

  .flash.error {
    background: rgba(248, 113, 113, 0.1);
    color: var(--fail);
    border: 1px solid rgba(248, 113, 113, 0.25);
  }

  .messages-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: 8px;
  }

  .messages-list li {
    background: var(--surface);
    border: 1px solid var(--surface-line);
    border-radius: 10px;
    padding: 12px 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
  }

  .messages-list .msg-text {
    font-size: 14px;
  }

  .messages-list .msg-time {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    color: var(--text-muted);
    white-space: nowrap;
  }

  .empty-state {
    color: var(--text-muted);
    font-size: 13px;
    font-family: 'JetBrains Mono', monospace;
    padding: 16px 0;
  }
</style>
</head>
<body>
  <div class="wrap">
    <span class="eyebrow"><span class="dot"></span>desafio docker · umbler</span>
    <h1>Ambiente <span>no ar.</span></h1>
    <p class="subhead">
      Nginx, PHP-FPM e MariaDB orquestrados via <code>docker compose</code>,
      cada serviço no seu próprio container, conectados por uma rede interna.
    </p>

    <div class="topology" aria-hidden="true">
      <div class="node"><div class="node-dot"></div>Nginx</div>
      <div class="link"></div>
      <div class="node"><div class="node-dot"></div>PHP-FPM</div>
      <div class="link"></div>
      <div class="node"><div class="node-dot"></div>MariaDB</div>
    </div>

    <div class="cards">
      <?php foreach ($services as $s): ?>
      <div class="card">
        <div class="card-left">
          <span class="status-dot <?= $s['status'] === 'ok' ? 'ok' : ($s['status'] === 'falha' ? 'falha' : 'atencao') ?>"></span>
          <div>
            <div class="card-name"><?= htmlspecialchars($s['name']) ?></div>
            <div class="card-role"><?= htmlspecialchars($s['role']) ?></div>
          </div>
        </div>
        <div>
          <div class="card-status-label <?= $s['status'] === 'ok' ? 'ok' : ($s['status'] === 'falha' ? 'falha' : 'atencao') ?>">
            <?= htmlspecialchars(strtoupper($s['status'])) ?>
          </div>
          <div class="card-detail"><?= htmlspecialchars($s['detail']) ?></div>
        </div>
      </div>
      <?php endforeach; ?>
    </div>

    <h2 class="section-title">Teste de persistência</h2>
    <p class="section-hint">
      Grave uma mensagem, depois rode <code>docker compose down</code> (sem <code>-v</code>) e
      <code>docker compose up -d</code> de novo. Se a mensagem continuar aparecendo aqui, o volume
      do MariaDB está persistindo os dados corretamente.
    </p>

    <?php if ($formSuccess): ?>
      <div class="flash success"><?= htmlspecialchars($formSuccess) ?></div>
    <?php elseif ($formError): ?>
      <div class="flash error"><?= htmlspecialchars($formError) ?></div>
    <?php endif; ?>

    <?php if ($dbOk): ?>
      <form class="persist-form" method="POST">
        <input type="text" name="texto" placeholder="Escreva algo para testar a persistência..." maxlength="255" required>
        <button type="submit">Gravar</button>
      </form>

      <ul class="messages-list">
        <?php if (empty($mensagens)): ?>
          <li class="empty-state">Nenhuma mensagem gravada ainda.</li>
        <?php else: ?>
          <?php foreach ($mensagens as $m): ?>
            <li>
              <span class="msg-text">#<?= (int)$m['id'] ?> — <?= htmlspecialchars($m['texto']) ?></span>
              <span class="msg-time"><?= htmlspecialchars($m['criado_em']) ?></span>
            </li>
          <?php endforeach; ?>
        <?php endif; ?>
      </ul>
    <?php else: ?>
      <div class="flash error">Conexão com o banco indisponível — corrija o card do MariaDB acima antes de testar a persistência.</div>
    <?php endif; ?>

    <footer>
      <span>PHP <?= htmlspecialchars($phpVersion) ?></span>
      <span>gerado em <?= htmlspecialchars($generatedAt) ?></span>
    </footer>
  </div>
</body>
</html>
