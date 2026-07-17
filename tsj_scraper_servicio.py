#!/usr/bin/env python3
"""
Consulta las decisiones del TSJ mediante el servicio interno utilizado por
la página oficial y convierte las sentencias HTML encontradas a PDF.

No recorre números consecutivos ni rastrea el índice histórico. Abre una sola
vez la página de decisiones del TSJ y reutiliza su función JavaScript
getDataFromServer() para llamar a:

    endpoint: /services/WSDecision.HTTPEndpoint
    method:   /listDecisionByFechaSala
    params:   FECHA, SALA

Instalación:
    py -m pip install playwright
    py -m playwright install chromium

Ejemplos:
    # Sala Plena, todo 2026 hasta la fecha actual
    py tsj_scraper_servicio.py --sala 001 --year 2026 --output Sala_Plena_2026

    # Probar sólo el 5 de febrero de 2026
    py tsj_scraper_servicio.py --sala 001 --date 2026-02-05 --output Prueba_TSJ

    # Sólo descubrir y guardar URL/metadatos
    py tsj_scraper_servicio.py --sala 001 --year 2026 --discover-only

    # Convertir una lista manual de URL, sin consultar el servicio
    py tsj_scraper_servicio.py --urls urls.txt --output PDFs_TSJ
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import unquote, urlparse, urlunparse

from playwright.async_api import (
    Browser,
    BrowserContext,
    Error as PlaywrightError,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

PORTAL_URL = "https://www.tsj.gob.ve/es/web/tsj/decisiones"
PORTLET_URL = (
    "https://www.tsj.gob.ve/es/decisiones"
    "?p_p_id=displayListaDecision_WAR_NoticiasTsjPorlet612"
    "&p_p_lifecycle=2"
    "&p_p_state=normal"
    "&p_p_mode=view"
    "&p_p_cacheability=cacheLevelPage"
    "&p_p_col_id=column-1"
    "&p_p_col_pos=1"
    "&p_p_col_count=2"
)
HISTORICAL_BASE = "https://historico.tsj.gob.ve/decisiones"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)

PRINT_CSS = r"""
@page {
  size: A4;
  margin: 13mm 12mm 15mm 12mm;
}
html, body {
  -webkit-print-color-adjust: exact !important;
  print-color-adjust: exact !important;
}
img, table {
  max-width: 100% !important;
}
pre, code {
  white-space: pre-wrap !important;
  overflow-wrap: anywhere !important;
}
"""

DATE_FORMATS = {
    "dmy": "%d/%m/%Y",
    "ymd": "%Y-%m-%d",
    "dmy-dash": "%d-%m-%Y",
}


@dataclass
class Decision:
    fecha_consultada: str
    url: str
    sala_codigo: str = ""
    sala: str = ""
    sala_directorio: str = ""
    mes: str = ""
    documento: str = ""
    numero_sentencia: str = ""
    expediente: str = ""
    fecha_sentencia: str = ""
    procedimiento: str = ""
    partes: str = ""
    ponente: str = ""
    decision: str = ""


@dataclass
class PdfResult:
    url: str
    pdf: str = ""
    title: str = ""
    status: str = ""
    error: str = ""


def text(value: Any) -> str:
    """Convierte valores del servicio a texto sin propagar None."""
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value).strip()


def canonicalize_url(url: str) -> str:
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower() or "https"
    host = parsed.netloc.lower()
    path = re.sub(r"/{2,}", "/", parsed.path)
    return urlunparse((scheme, host, path, "", parsed.query, ""))


def is_decision_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.netloc.lower() not in {
        "historico.tsj.gob.ve",
        "www.historico.tsj.gob.ve",
    }:
        return False

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 4 or parts[0].lower() != "decisiones":
        return False

    filename = parts[-1].lower()
    return filename.endswith((".htm", ".html")) and filename not in {
        "decisiones.html",
        "decisiones.htm",
        "index.html",
        "index.htm",
    }


def build_decision_url(item: dict[str, Any]) -> str | None:
    sala_dir = text(item.get("SSALADIR")).strip("/")
    month = text(item.get("NOMBREMES")).strip().strip("/")
    document = text(item.get("SSENTNOMBREDOC")).strip().strip("/")

    if not sala_dir or not month or not document:
        return None
    if document.lower() == "null":
        return None

    url = f"{HISTORICAL_BASE}/{sala_dir}/{month}/{document}"
    url = canonicalize_url(url)
    return url if is_decision_url(url) else None


def normalize_collection(payload: Any) -> list[dict[str, Any]]:
    """
    Extrae coleccion.SENTENCIA. El portal devuelve a veces un objeto cuando
    sólo hay una sentencia y una lista cuando hay varias.
    """
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            return []

    if not isinstance(payload, dict):
        return []

    collection = payload.get("coleccion")
    if not isinstance(collection, dict):
        return []

    sentences = collection.get("SENTENCIA")
    if sentences in (None, "", "null"):
        return []
    if isinstance(sentences, dict):
        return [sentences]
    if isinstance(sentences, list):
        return [item for item in sentences if isinstance(item, dict)]
    return []


def decision_from_item(
    item: dict[str, Any],
    queried_date: str,
    sala_code: str,
) -> Decision | None:
    url = build_decision_url(item)
    if not url:
        return None

    return Decision(
        fecha_consultada=queried_date,
        url=url,
        sala_codigo=sala_code,
        sala=text(item.get("SSALADESCRIPCION")),
        sala_directorio=text(item.get("SSALADIR")),
        mes=text(item.get("NOMBREMES")),
        documento=text(item.get("SSENTNOMBREDOC")),
        numero_sentencia=text(item.get("SSENTNUMERO")),
        expediente=text(item.get("SSENTEXPEDIENTE")),
        fecha_sentencia=text(item.get("DSENTFECHA")),
        procedimiento=text(item.get("SPROCDESCRIPCION")),
        partes=text(item.get("SSENTPARTES")),
        ponente=text(item.get("SPONENOMBRE")),
        decision=text(item.get("SSENTDECISION")),
    )


async def goto_with_retries(
    page: Page,
    url: str,
    timeout_ms: int,
    retries: int = 3,
) -> None:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
            return
        except (PlaywrightTimeoutError, PlaywrightError) as exc:
            last_error = exc
            if attempt < retries:
                await asyncio.sleep(attempt * 2)

    assert last_error is not None
    raise last_error


async def prepare_service_page(
    context: BrowserContext,
    timeout_ms: int,
) -> Page:
    """
    Abre el portal una sola vez y espera a que esté disponible la función
    getDataFromServer incluida por los scripts del TSJ.
    """
    page = await context.new_page()
    print(f"Abriendo una sola vez el portal: {PORTAL_URL}")
    await goto_with_retries(page, PORTAL_URL, timeout_ms)

    try:
        await page.wait_for_function(
            "typeof window.getDataFromServer === 'function'",
            timeout=timeout_ms,
        )
    except PlaywrightTimeoutError as exc:
        await page.close()
        raise RuntimeError(
            "La página abrió, pero no apareció getDataFromServer(). "
            "Pruebe con --headed para comprobar si el portal mostró un error."
        ) from exc

    return page


async def query_service(
    page: Page,
    fecha: str,
    sala: str,
    timeout_ms: int,
) -> Any:
    """
    Ejecuta en el navegador la misma llamada que hace loadDataDesicion().
    De esta forma no es necesario adivinar el formato interno del POST.
    """
    js_timeout = max(5_000, timeout_ms)

    return await page.evaluate(
        """
        async ({portletUrl, fecha, sala, timeoutMs}) => {
            return await new Promise((resolve, reject) => {
                let finished = false;

                const timer = setTimeout(() => {
                    if (!finished) {
                        finished = true;
                        reject(new Error(
                            "Tiempo agotado consultando listDecisionByFechaSala"
                        ));
                    }
                }, timeoutMs);

                const finish = (data) => {
                    if (finished) return;
                    finished = true;
                    clearTimeout(timer);
                    resolve(data);
                };

                try {
                    if (typeof window.getDataFromServer !== "function") {
                        throw new Error("getDataFromServer no está disponible");
                    }

                    window.getDataFromServer(
                        finish,
                        {
                            url: portletUrl,
                            server: {
                                endpoint: "/services/WSDecision.HTTPEndpoint",
                                method: "/listDecisionByFechaSala"
                            },
                            params: {
                                FECHA: fecha,
                                SALA: sala
                            }
                        }
                    );
                } catch (error) {
                    if (!finished) {
                        finished = true;
                        clearTimeout(timer);
                        reject(error);
                    }
                }
            });
        }
        """,
        {
            "portletUrl": PORTLET_URL,
            "fecha": fecha,
            "sala": sala,
            "timeoutMs": js_timeout,
        },
    )


def make_date_range(args: argparse.Namespace) -> list[date]:
    if args.date:
        return sorted({datetime.strptime(value, "%Y-%m-%d").date() for value in args.date})

    year = args.year
    start = (
        datetime.strptime(args.start, "%Y-%m-%d").date()
        if args.start
        else date(year, 1, 1)
    )
    end = (
        datetime.strptime(args.end, "%Y-%m-%d").date()
        if args.end
        else date(year, 12, 31)
    )

    # Evita consultar fechas futuras del año en curso salvo que --end las pida.
    if not args.end and year == date.today().year:
        end = date.today()

    if end < start:
        raise ValueError("La fecha final no puede ser anterior a la inicial.")

    days: list[date] = []
    current = start
    while current <= end:
        days.append(current)
        current += timedelta(days=1)
    return days


async def discover_via_service(
    page: Page,
    sala: str,
    dates: Iterable[date],
    date_format: str,
    timeout_ms: int,
    delay: float,
    save_json_dir: Path | None,
) -> list[Decision]:
    found_by_url: dict[str, Decision] = {}
    dates = list(dates)
    total = len(dates)

    if save_json_dir:
        save_json_dir.mkdir(parents=True, exist_ok=True)

    for index, current_date in enumerate(dates, start=1):
        fecha = current_date.strftime(date_format)
        print(f"[FECHA {index:03d}/{total:03d}] {fecha}")

        try:
            payload = await query_service(
                page=page,
                fecha=fecha,
                sala=sala,
                timeout_ms=timeout_ms,
            )
        except Exception as exc:
            print(
                f"  ! Error consultando la fecha: {type(exc).__name__}: {exc}",
                file=sys.stderr,
            )
            if delay:
                await asyncio.sleep(delay)
            continue

        if save_json_dir:
            json_path = save_json_dir / f"{current_date.isoformat()}.json"
            json_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        items = normalize_collection(payload)
        valid_count = 0

        for item in items:
            decision = decision_from_item(item, fecha, sala)
            if decision is None:
                continue
            found_by_url.setdefault(decision.url, decision)
            valid_count += 1

        if valid_count:
            print(
                f"  -> {valid_count} sentencia(s); "
                f"{len(found_by_url)} URL únicas acumuladas"
            )

        if delay:
            await asyncio.sleep(delay)

    return sorted(
        found_by_url.values(),
        key=lambda item: (
            item.fecha_sentencia or item.fecha_consultada,
            item.numero_sentencia,
            item.url,
        ),
    )


def safe_filename_from_url(url: str) -> str:
    parsed = urlparse(url)
    filename = unquote(Path(parsed.path).name)
    stem = re.sub(r"\.(?:html?)$", "", filename, flags=re.IGNORECASE)
    stem = re.sub(r"[^0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ._-]+", "_", stem)
    stem = stem.strip("._-") or "decision"
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:8]
    return f"{stem}_{digest}.pdf"


async def page_title(page: Page) -> str:
    try:
        title = (await page.title()).strip()
        if title:
            return title
    except PlaywrightError:
        pass
    return ""


async def convert_one_to_pdf(
    page: Page,
    url: str,
    output_dir: Path,
    timeout_ms: int,
    overwrite: bool,
) -> PdfResult:
    pdf_path = output_dir / safe_filename_from_url(url)
    result = PdfResult(url=url, pdf=str(pdf_path))

    if pdf_path.exists() and not overwrite:
        result.status = "omitido_existente"
        return result

    try:
        await goto_with_retries(page, url, timeout_ms)
        await page.emulate_media(media="screen")
        await page.add_style_tag(content=PRINT_CSS)

        try:
            await page.wait_for_function(
                "document.readyState === 'complete'",
                timeout=min(timeout_ms, 10_000),
            )
        except PlaywrightTimeoutError:
            pass

        await page.wait_for_timeout(700)
        result.title = await page_title(page)

        await page.pdf(
            path=str(pdf_path),
            format="A4",
            print_background=True,
            prefer_css_page_size=False,
            display_header_footer=False,
            margin={
                "top": "13mm",
                "right": "12mm",
                "bottom": "15mm",
                "left": "12mm",
            },
        )
        result.status = "descargado"
    except Exception as exc:
        result.status = "error"
        result.error = f"{type(exc).__name__}: {exc}"

    return result


async def convert_urls(
    context: BrowserContext,
    urls: Iterable[str],
    output_dir: Path,
    timeout_ms: int,
    overwrite: bool,
    delay: float,
) -> list[PdfResult]:
    output_dir.mkdir(parents=True, exist_ok=True)
    page = await context.new_page()
    results: list[PdfResult] = []

    try:
        for number, url in enumerate(urls, start=1):
            print(f"[PDF {number:04d}] {url}")
            result = await convert_one_to_pdf(
                page=page,
                url=url,
                output_dir=output_dir,
                timeout_ms=timeout_ms,
                overwrite=overwrite,
            )
            results.append(result)

            if result.status == "error":
                print(f"  ! {result.error}", file=sys.stderr)
            else:
                print(f"  -> {result.status}: {result.pdf}")

            if delay:
                await asyncio.sleep(delay)
    finally:
        await page.close()

    return results


def write_decisions_csv(path: Path, decisions: Iterable[Decision]) -> None:
    decisions = list(decisions)
    fields = list(Decision.__dataclass_fields__.keys())

    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for decision in decisions:
            writer.writerow(asdict(decision))


def write_pdf_manifest(path: Path, results: Iterable[PdfResult]) -> None:
    fields = list(PdfResult.__dataclass_fields__.keys())
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in results:
            writer.writerow(asdict(result))


def write_url_list(path: Path, urls: Iterable[str]) -> None:
    urls = list(urls)
    content = "\n".join(urls)
    if content:
        content += "\n"
    path.write_text(content, encoding="utf-8")


def read_urls_file(path: Path) -> list[str]:
    urls: list[str] = []

    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        url = canonicalize_url(line)
        if is_decision_url(url):
            urls.append(url)
        else:
            print(
                f"Se ignora una URL que no parece una sentencia: {line}",
                file=sys.stderr,
            )

    return sorted(set(urls))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Consulta el servicio interno de decisiones del TSJ y convierte "
            "las sentencias HTML encontradas a PDF."
        )
    )

    parser.add_argument(
        "--urls",
        type=Path,
        help="Lista manual de URL; omite completamente la consulta al servicio.",
    )
    parser.add_argument(
        "--sala",
        default="001",
        help=(
            "Código enviado como SALA. Para Sala Plena se usa inicialmente 001. "
            "Si el portal no devuelve resultados, pruebe también 1."
        ),
    )
    parser.add_argument(
        "--year",
        type=int,
        default=date.today().year,
        help="Año a consultar cuando no se indican fechas concretas.",
    )
    parser.add_argument(
        "--date",
        action="append",
        help=(
            "Fecha concreta en formato AAAA-MM-DD. Puede repetirse varias veces. "
            "Ejemplo: --date 2026-02-05"
        ),
    )
    parser.add_argument(
        "--start",
        help="Fecha inicial en formato AAAA-MM-DD.",
    )
    parser.add_argument(
        "--end",
        help="Fecha final en formato AAAA-MM-DD.",
    )
    parser.add_argument(
        "--date-format",
        choices=sorted(DATE_FORMATS),
        default="dmy",
        help=(
            "Formato enviado al servicio: dmy=05/02/2026, "
            "ymd=2026-02-05, dmy-dash=05-02-2026."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("TSJ_PDF"),
        help="Carpeta de salida.",
    )
    parser.add_argument(
        "--discover-only",
        action="store_true",
        help="Guarda URL y metadatos, pero no genera PDF.",
    )
    parser.add_argument(
        "--save-json",
        action="store_true",
        help="Guarda la respuesta del servicio para cada fecha.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Regenera PDF que ya existen.",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Muestra Chromium para diagnosticar errores del portal.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=45,
        help="Tiempo máximo por consulta o página, en segundos.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.25,
        help="Pausa entre consultas y descargas, en segundos.",
    )

    return parser.parse_args()


async def async_main(args: argparse.Namespace) -> int:
    output_dir: Path = args.output
    output_dir.mkdir(parents=True, exist_ok=True)
    timeout_ms = max(1, args.timeout) * 1000
    delay = max(0.0, args.delay)

    async with async_playwright() as playwright:
        browser: Browser = await playwright.chromium.launch(
            headless=not args.headed,
            args=["--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            ignore_https_errors=True,
            user_agent=USER_AGENT,
            locale="es-VE",
            viewport={"width": 1440, "height": 1100},
        )

        try:
            decisions: list[Decision] = []

            if args.urls:
                urls = read_urls_file(args.urls)
            else:
                dates = make_date_range(args)
                print(
                    f"Consultando SALA={args.sala}; "
                    f"{len(dates)} fecha(s); formato={args.date_format}"
                )

                service_page = await prepare_service_page(context, timeout_ms)
                try:
                    decisions = await discover_via_service(
                        page=service_page,
                        sala=args.sala,
                        dates=dates,
                        date_format=DATE_FORMATS[args.date_format],
                        timeout_ms=timeout_ms,
                        delay=delay,
                        save_json_dir=(
                            output_dir / "respuestas_json"
                            if args.save_json
                            else None
                        ),
                    )
                finally:
                    await service_page.close()

                urls = [decision.url for decision in decisions]

                metadata_path = output_dir / "sentencias.csv"
                write_decisions_csv(metadata_path, decisions)
                print(f"Metadatos: {metadata_path}")

            urls = sorted(set(urls))
            url_list_path = output_dir / "decisiones_encontradas.txt"
            write_url_list(url_list_path, urls)

            print(f"\nDecisiones únicas encontradas: {len(urls)}")
            print(f"Lista de URL: {url_list_path}")

            if not urls:
                print(
                    "\nNo se encontraron decisiones. Para Sala Plena pruebe primero:\n"
                    "  --date 2026-02-05 --sala 001\n"
                    "y, si sigue vacío:\n"
                    "  --date 2026-02-05 --sala 1\n"
                    "También puede probar --date-format ymd o --headed.",
                    file=sys.stderr,
                )
                return 2

            if args.discover_only:
                return 0

            results = await convert_urls(
                context=context,
                urls=urls,
                output_dir=output_dir,
                timeout_ms=timeout_ms,
                overwrite=args.overwrite,
                delay=delay,
            )

            manifest_path = output_dir / "manifiesto_pdf.csv"
            write_pdf_manifest(manifest_path, results)

            errors = sum(item.status == "error" for item in results)
            downloaded = sum(item.status == "descargado" for item in results)
            skipped = sum(item.status == "omitido_existente" for item in results)

            print(
                f"\nTerminó: {downloaded} descargadas, "
                f"{skipped} omitidas y {errors} errores."
            )
            print(f"Manifiesto PDF: {manifest_path}")
            return 1 if errors else 0

        finally:
            await context.close()
            await browser.close()


def main() -> int:
    args = parse_args()

    try:
        return asyncio.run(async_main(args))
    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario.", file=sys.stderr)
        return 130
    except ValueError as exc:
        print(f"Error de parámetros: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"Error fatal: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
