@echo off
setlocal
rem Atalhos da pesquisa. Uso: .\pesquisa contar ^| limpar ^| exportar ^| analisar ^| publicar
set "DB=pesquisa-senhas-pucminas-db"
cd /d "%~dp0"

if /i "%~1"=="contar"   goto count
if /i "%~1"=="limpar"   goto clear
if /i "%~1"=="exportar" goto export
if /i "%~1"=="analisar" goto analyze
if /i "%~1"=="publicar" goto deploy
goto help

:count
call npx.cmd wrangler d1 execute %DB% --remote --command "SELECT COUNT(*) AS total FROM responses"
goto :eof

:clear
echo.
echo ATENCAO: isto apaga TODAS as respostas do banco e nao tem volta.
set "CONFIRM="
set /p "CONFIRM=Digite APAGAR para confirmar: "
if not "%CONFIRM%"=="APAGAR" (
  echo Cancelado. Nada foi apagado.
  goto :eof
)
call npx.cmd wrangler d1 execute %DB% --remote --command "DELETE FROM responses"
goto :eof

:export
call npx.cmd wrangler d1 execute %DB% --remote --json --command "SELECT * FROM responses ORDER BY id" > export.json
if errorlevel 1 (
  echo Erro ao exportar. Veja a mensagem acima.
  goto :eof
)
python scripts\export_results.py export.json
goto :eof

:analyze
python scripts\analyze_results.py
goto :eof

:deploy
call npx.cmd wrangler pages deploy
goto :eof

:help
echo.
echo Uso: .\pesquisa ^<comando^>
echo.
echo   contar     mostra quantas respostas ja chegaram
echo   limpar     apaga TODAS as respostas (pede confirmacao)
echo   exportar   baixa as respostas para export.json e gera o results.csv
echo   analisar   roda a analise estatistica (resultado na pasta output)
echo   publicar   publica a pagina e a API na Cloudflare
echo.
