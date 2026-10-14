import io
from datetime import date, timedelta

import pandas as pd

import database
import seed
from services import patient_service, report_service
from utils.export_utils import to_csv_bytes, to_excel_bytes


def test_t16_empty_dashboard(admin):
    m = report_service.dashboard_metrics(admin)
    assert m["patients_total"] == 0 and m["beds_available"] == 0 and m["outstanding"] == 0
    charts = report_service.dashboard_charts(admin)
    assert all(df.empty for df in charts.values())


def test_t18_data_persists_across_connections(admin, temp_db):
    patient_service.register(admin, {"full_name": "Persistent Person"})
    database.init_db()  # simulates an app restart
    assert patient_service.search(admin, "Persistent")[0]["full_name"] == "Persistent Person"


def test_t19_backup_and_restore(admin, tmp_path):
    patient_service.register(admin, {"full_name": "Before Backup"})
    backup = database.backup_to(tmp_path / "backups" / "b.db")
    database.validate_backup(backup)
    patient_service.register(admin, {"full_name": "After Backup"})
    database.restore_from(backup)
    names = [p["full_name"] for p in patient_service.search(admin)]
    assert names == ["Before Backup"]


def test_restore_rejects_non_database(tmp_path):
    bad = tmp_path / "bad.db"
    bad.write_bytes(b"not a database at all" * 100)
    import pytest
    with pytest.raises(ValueError):
        database.restore_from(bad)


def test_t20_export_respects_filters_and_columns(admin):
    patient_service.register(admin, {"full_name": "=HYPERLINK(\"http://x\")", "phone": "9000000001"})
    patient_service.register(admin, {"full_name": "Plain Name"})
    df = report_service.run_report(admin, "patients", date.today(), date.today())
    assert len(df) == 2
    csv = to_csv_bytes(df, ["full_name"]).decode("utf-8-sig")
    assert csv.splitlines()[0] == "full_name"
    assert "'=HYPERLINK" in csv and "phone" not in csv
    xlsx = pd.read_excel(io.BytesIO(to_excel_bytes(df, ["full_name", "phone"])))
    assert list(xlsx.columns) == ["full_name", "phone"]
    old = report_service.run_report(admin, "patients", date.today() - timedelta(days=10),
                                    date.today() - timedelta(days=5))
    assert old.empty


def test_demo_seed_respects_all_invariants():
    seed.seed_demo()
    from services import auth_service, pharmacy_service
    admin = auth_service.authenticate("admin", "Admin@123")
    m = report_service.dashboard_metrics(admin)
    assert m["patients_total"] > 0 and m["admissions_current"] > 0
    assert m["low_stock"] > 0 and m["expiring_batches"] > 0
    assert pharmacy_service.reconciliation_mismatches(admin) == []
    for key in report_service.available_reports(admin):
        report_service.run_report(admin, key, date.today() - timedelta(days=60), date.today())
