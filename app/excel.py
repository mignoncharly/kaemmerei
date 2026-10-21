"""Minimal XLSX import/export support using Python's standard library."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from io import BytesIO
import posixpath
import re
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG = "http://schemas.openxmlformats.org/package/2006/relationships"
MAX_XLSX_UNCOMPRESSED = 20 * 1024 * 1024
MAX_IMPORT_ROWS = 500

EXPORT_COLUMNS = (
    ("contract_number", "Vertragsnummer"),
    ('external_reference', 'External reference'),
    ('value_basis', 'Value basis (net/gross/unknown)'),
    ("designation", "Bezeichnung"),
    ("contract_type", "Vertragsart"),
    ("contract_partner", "Vertragspartner"),
    ("relevant_date", "Vertragsbeginn (JJJJ-MM-TT)"),
    ("end_date", "Vertragsende (JJJJ-MM-TT)"),
    ("notice_period_months", "Kündigungsfrist (Monate)"),
    ("automatic_renewal", "Automatische Verlängerung (Ja/Nein)"),
    ("renewal_period_months", "Verlängerungszeitraum (Monate)"),
    ("annual_value", "Jahreswert (EUR)"),
    ("contract_value", "Gesamtvertragswert (EUR)"),
    ("financial_direction", "Einnahme oder Ausgabe"),
    ("payment_interval", "Zahlungsintervall"),
    ("budget_assignment", "Haushaltszuordnung / Produktkonto"),
    ("tax_review_status", "§ 2b UStG-Prüfstatus"),
    ("tax_review_result", "§ 2b UStG-Prüfergebnis"),
    ("contact_person", "Zuständige Person"),
    ("deputy_contact_person", "Vertretung"),
    ("status", "Vertragsstatus"),
    ("is_archived", "Archiviert (Ja/Nein)"),
    ("department", "Fachbereich"),
)

HEADER_ALIASES = {
    'external reference': 'external_reference', 'external_reference': 'external_reference',
    'value basis (net/gross/unknown)': 'value_basis', 'value_basis': 'value_basis',
    "bezeichnung": "designation", "designation": "designation",
    "vertragsnummer": "contract_number", "contract_number": "contract_number",
    "vertragsart": "contract_type", "contract_type": "contract_type",
    "vertragspartner": "contract_partner", "contract_partner": "contract_partner",
    "vertragsbeginn (jjjj-mm-tt)": "relevant_date", "vertragsbeginn": "relevant_date",
    "relevant_date": "relevant_date", "vertragsende (jjjj-mm-tt)": "end_date",
    "vertragsende": "end_date", "end_date": "end_date",
    "kündigungsfrist (monate)": "notice_period_months", "kündigungsfrist": "notice_period_months",
    "notice_period_months": "notice_period_months",
    "automatische verlängerung (ja/nein)": "automatic_renewal", "automatische verlängerung": "automatic_renewal",
    "automatic_renewal": "automatic_renewal", "verlängerungszeitraum (monate)": "renewal_period_months",
    "verlängerungszeitraum": "renewal_period_months", "renewal_period_months": "renewal_period_months",
    "jahreswert (eur)": "annual_value", "jahreswert": "annual_value", "annual_value": "annual_value",
    "gesamtvertragswert (eur)": "contract_value", "gesamtvertragswert": "contract_value", "contract_value": "contract_value",
    "einnahme oder ausgabe": "financial_direction", "financial_direction": "financial_direction",
    "zahlungsintervall": "payment_interval", "payment_interval": "payment_interval",
    "haushaltszuordnung / produktkonto": "budget_assignment", "haushaltszuordnung": "budget_assignment",
    "budget_assignment": "budget_assignment", "§ 2b ustg-prüfstatus": "tax_review_status",
    "tax_review_status": "tax_review_status", "§ 2b ustg-prüfergebnis": "tax_review_result",
    "tax_review_result": "tax_review_result", "zuständige person": "contact_person",
    "contact_person": "contact_person", "vertretung": "deputy_contact_person",
    "deputy_contact_person": "deputy_contact_person", "vertragsstatus": "status", "status": "status",
    "fachbereich": "department", "department": "department",
    "archiviert (ja/nein)": "is_archived", "archiviert": "is_archived", "is_archived": "is_archived",
}


def _column_name(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _cell_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.date().isoformat() if isinstance(value, datetime) else value.isoformat()
    if isinstance(value, bool):
        return "Ja" if value else "Nein"
    return str(value).strip()


def _worksheet_xml(rows) -> bytes:
    root = ET.Element(f"{{{NS_MAIN}}}worksheet")
    sheet_data = ET.SubElement(root, f"{{{NS_MAIN}}}sheetData")
    for row_number, row in enumerate(rows, 1):
        row_node = ET.SubElement(sheet_data, f"{{{NS_MAIN}}}row", {"r": str(row_number)})
        for col_number, value in enumerate(row, 1):
            if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
                cell = ET.SubElement(row_node, f"{{{NS_MAIN}}}c", {
                    "r": f"{_column_name(col_number)}{row_number}"})
                ET.SubElement(cell, f"{{{NS_MAIN}}}v").text = str(value)
                continue
            text = _cell_text(value)
            cell = ET.SubElement(row_node, f"{{{NS_MAIN}}}c", {
                "r": f"{_column_name(col_number)}{row_number}", "t": "inlineStr"})
            inline = ET.SubElement(cell, f"{{{NS_MAIN}}}is")
            node = ET.SubElement(inline, f"{{{NS_MAIN}}}t")
            if text != text.strip():
                node.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
            node.text = text
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def make_xlsx(headers: list[str], rows: list[list[object]]) -> bytes:
    content_types = (b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                     b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                     b'<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                     b'<Default Extension="xml" ContentType="application/xml"/>'
                     b'<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                     b'<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                     b'</Types>')
    root_rels = (b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                 b'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                 b'</Relationships>')
    workbook = (b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                b'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                b'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                b'<sheets><sheet name="Vertraege" sheetId="1" r:id="rId1"/></sheets></workbook>')
    workbook_rels = (b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                     b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                     b'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
                     b'</Relationships>')
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/worksheets/sheet1.xml", _worksheet_xml([headers, *rows]))
    return output.getvalue()


def _read_cell(cell, shared_strings: list[str]):
    if cell.find(f"{{{NS_MAIN}}}f") is not None:
        raise ValueError('Formula cells are not supported; paste literal values first.')
    kind = cell.get("t")
    if kind == 'e':
        raise ValueError('Excel error cell; replace with a literal value.')
    if kind == "inlineStr":
        return "".join(node.text or "" for node in cell.findall(f".//{{{NS_MAIN}}}t"))
    value_node = cell.find(f"{{{NS_MAIN}}}v")
    value = value_node.text if value_node is not None and value_node.text else ""
    if kind == "s" and value:
        try:
            index = int(value)
            if index < 0:
                raise ValueError('Negative shared string index')
            return shared_strings[index]
        except (ValueError, IndexError):
            raise ValueError("Die Excel-Datei enthält einen ungültigen Textverweis.")
    return value


def read_xlsx(data: bytes) -> list[tuple[int, dict[str, str]]]:
    try:
        archive = ZipFile(BytesIO(data))
    except BadZipFile as exc:
        raise ValueError("Die Datei ist keine gültige .xlsx-Arbeitsmappe.") from exc
    with archive:
        if len(archive.infolist()) > 1000 or len(set(archive.namelist())) != len(archive.namelist()):
            raise ValueError('Too many ZIP members or duplicate ZIP paths.')
        if sum(item.file_size for item in archive.infolist()) > MAX_XLSX_UNCOMPRESSED:
            raise ValueError("Die entpackte Excel-Datei ist zu groß.")
        try:
            workbook = ET.fromstring(archive.read("xl/workbook.xml"))
            rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        except (KeyError, ET.ParseError) as exc:
            raise ValueError("Die Excel-Datei enthält keine gültige Arbeitsmappe.") from exc
        properties = workbook.find(f'{{{NS_MAIN}}}workbookPr')
        if properties is not None and properties.get('date1904', '0').lower() not in ('0', 'false'):
            raise ValueError('1904 workbook date system is not supported; use ISO date strings in a 1900 workbook.')
        sheet = workbook.find(f".//{{{NS_MAIN}}}sheet")
        if sheet is None:
            raise ValueError("Die Arbeitsmappe enthält kein Tabellenblatt.")
        relationship_id = sheet.get(f"{{{NS_REL}}}id")
        relation = next((item for item in rels.findall(f"{{{NS_PKG}}}Relationship")
                         if item.get("Id") == relationship_id), None)
        if relation is None or relation.get("TargetMode") == "External":
            raise ValueError("Das Tabellenblatt konnte nicht geöffnet werden.")
        target = relation.get("Target", "")
        sheet_path = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join("xl", target))
        if not sheet_path.startswith('xl/worksheets/') or not sheet_path.endswith('.xml'):
            raise ValueError('Invalid worksheet relationship target.')
        try:
            sheet_root = ET.fromstring(archive.read(sheet_path))
        except (KeyError, ET.ParseError) as exc:
            raise ValueError("Das Excel-Tabellenblatt ist beschädigt.") from exc
        try:
            shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared_strings = ["".join(node.text or "" for node in item.findall(f".//{{{NS_MAIN}}}t"))
                              for item in shared_root.findall(f"{{{NS_MAIN}}}si")]
        except KeyError:
            shared_strings = []
        except ET.ParseError as exc:
            raise ValueError("Die Excel-Texttabelle ist beschädigt.") from exc
    sheet_data = sheet_root.find(f"{{{NS_MAIN}}}sheetData")
    if sheet_data is None:
        raise ValueError("Das erste Tabellenblatt enthält keine Daten.")
    parsed_rows = []
    previous_row = 0
    for row in sheet_data.findall(f"{{{NS_MAIN}}}row"):
        try:
            row_number = int(row.get('r', str(previous_row + 1)))
        except ValueError as exc:
            raise ValueError('Invalid worksheet row number.') from exc
        if not previous_row < row_number <= 1048576:
            raise ValueError('Invalid or repeated worksheet row number.')
        previous_row = row_number
        cells = {}
        for cell in row.findall(f"{{{NS_MAIN}}}c"):
            address = cell.get("r", "")
            match = re.fullmatch(r'([A-Z]{1,3})([1-9][0-9]{0,6})', address)
            if not match or int(match[2]) != row_number:
                raise ValueError(f'Row {row_number}: invalid cell reference {address[:20]}.')
            letters = match[1]
            col = 0
            for char in letters.upper():
                col = col * 26 + ord(char) - 64
            if col > 16384 or col in cells:
                raise ValueError(f'Row {row_number}: duplicate or out-of-range column.')
            try:
                cells[col] = _read_cell(cell, shared_strings)
            except ValueError as exc:
                raise ValueError(f'Row {row_number}, {address}: {exc}') from exc
        parsed_rows.append((row_number, cells))
        if len(parsed_rows) > MAX_IMPORT_ROWS + 1:
            raise ValueError(f"Der Import ist auf {MAX_IMPORT_ROWS} Vertragszeilen begrenzt.")
    if not parsed_rows:
        raise ValueError("Das Tabellenblatt enthält keine Kopfzeile.")
    header_row = next(((number, cells) for number, cells in parsed_rows
                       if any(str(value).strip() for value in cells.values())), None)
    if not header_row:
        raise ValueError("Das Tabellenblatt enthält keine Kopfzeile.")
    header_number, header_cells = header_row
    columns = {}
    for col, title in header_cells.items():
        normalized = str(title).strip().casefold()
        field = HEADER_ALIASES.get(normalized)
        if normalized and field is None:
            raise ValueError(f'Unsupported column: {str(title)[:120]}. Remove it explicitly before importing.')
        if field:
            if field in columns:
                raise ValueError(f'Duplicate column: {field}')
            columns[field] = col
    required = {"designation", "contract_type", "relevant_date", "contact_person"}
    missing = sorted(required - set(columns))
    if missing:
        raise ValueError("Pflichtspalten fehlen: " + ", ".join(missing))
    result = []
    for row_number, cells in parsed_rows:
        if row_number <= header_number or not any(str(value).strip() for value in cells.values()):
            continue
        data_row = {field: str(cells.get(col, "")).strip() for field, col in columns.items()}
        result.append((row_number, data_row))
    if not result:
        raise ValueError("Die Arbeitsmappe enthält keine Vertragszeilen.")
    if len(result) > MAX_IMPORT_ROWS:
        raise ValueError(f"Der Import ist auf {MAX_IMPORT_ROWS} Vertragszeilen begrenzt.")
    return result


def excel_date(value: str) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    try:
        number = Decimal(value)
    except InvalidOperation:
        number = None
    if number is not None:
        if not number.is_finite() or number != number.to_integral_value() or not 1 <= number <= 2958465 or number == 60:
            raise ValueError('Invalid Excel date: use a whole supported day serial or ISO date; serial 60 is fictitious.')
        return (date(1899, 12, 31) + timedelta(days=int(number) - (1 if number > 60 else 0))).isoformat()
    for fmt in ("%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return value
