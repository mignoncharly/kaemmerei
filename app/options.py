"""Dropdown options for the contract entry form."""

CONTRACT_TYPES = (
    "Bauvertrag",
    "Dienstleistungsvertrag",
    "Kauf-/Liefervertrag",
    "Mietvertrag",
    "Pachtvertrag",
    "Rahmenvertrag",
    "Wartungsvertrag",
    "Werkvertrag",
    "Versicherungsvertrag",
    "Kooperationsvereinbarung",
    "Konzessionsvertrag",
    "Sonstiger Vertrag",
)

CONTRACT_STATUSES = (
    ("draft", "Entwurf"),
    ("in_progress", "In Abstimmung"),
    ("active", "Aktiv"),
    ("terminated", "Gekündigt"),
    ("ended", "Beendet/abgelaufen"),
)

TASK_KINDS = (
    ("review", "Prüfung"),
    ("complete", "Vervollständigung"),
    ("update", "Aktualisierung"),
    ("other", "Sonstige Aufgabe"),
)

TASK_STATUSES = (
    ("open", "Offen"),
    ("in_progress", "In Bearbeitung"),
    ("done", "Erledigt"),
)

FINANCIAL_DIRECTIONS = (
    ("expense", "Ausgabe"),
    ("income", "Einnahme"),
)

PAYMENT_INTERVALS = (
    ("one_time", "Einmalig"),
    ("monthly", "Monatlich"),
    ("quarterly", "Vierteljährlich"),
    ("semiannual", "Halbjährlich"),
    ("annual", "Jährlich"),
    ("irregular", "Unregelmäßig / nach Bedarf"),
)

TAX_REVIEW_STATUSES = (
    ("not_checked", "Noch nicht geprüft"),
    ("required", "Prüfung erforderlich"),
    ("in_progress", "In Prüfung"),
    ("completed", "Abgeschlossen"),
    ("not_applicable", "Nicht relevant"),
)

REVIEW_RECIPIENTS = (
    "Kämmerei",
    "Zuständiger Fachbereich",
    "Rechtsamt",
    "Datenschutz",
    "Sonstige Stelle",
)
CONTRACT_REVIEW_STATUSES = (
    ("open", "Zur Prüfung eingereicht"),
    ("in_review", "In Prüfung"),
    ("approved", "Freigegeben"),
    ("changes_requested", "Überarbeitung erforderlich"),
    ("rejected", "Abgelehnt"),
    ("withdrawn", "Zurückgezogen"),
)

CONTACT_PERSONS = (
    "Annette Arndt",
    "Nicole Baier",
    "Romy Bernhardt",
    "Manuela Bohnstädt",
    "Diana Cornelius",
    "Corinna Claußner",
    "Max Claußner",
    "Manuela Diecke",
    "Diana Enigk",
    "Christina Eule",
    "Karsten Eule-Prütz",
    "André Fleischer",
    "Ute Freywald",
    "Nancy Friedel",
    "Eileen Fröde",
    "Tim Gärtner",
    "Daniel Globig",
    "Barbara Gloel",
    "Birgit Göhler",
    "Anna Golm",
    "Jan Grüßner",
    "Michael Hartl",
    "Rita Heinrich",
    "Giulia Heyde",
    "Jessica Heyde",
    "Karin Jage",
    "Kirsten John",
    "Paul Kammer",
    "Philipp Kapusta",
    "André Keßler",
    "Yvonne Kettner",
    "Rene Kiepisch",
    "Katrin Kiepsch",
    "Doreen Klinkmüller",
    "Benjamin Kobow Lehmann",
    "Mario Kraske",
    "Stephanie Kuntze",
    "Jenny Kuring",
    "Dirk Laurig",
    "Frank Lehmann",
    "Vanessa Lehmann",
    "Diana Leitritz",
    "Lara Meyne",
    "Ronny Mischke",
    "Juliane Mühlbach",
    "Charles Nguenkam",
    "Benjamin Peter",
    "Franziska Preetz",
    "Danielle Runge",
    "Alexandra Scheffzyk",
    "Michael Schmidt",
    "Linda Scholsching",
    "Anja Stauber",
    "Judith Stets",
    "Ines Stottmeyer",
    "Pauline Uhlig",
    "Christopher Unger",
    "Bettina Weiß",
    "Simone Wittig",
    "Sven Ziehe",
)
