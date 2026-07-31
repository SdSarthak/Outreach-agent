"""Command line parsing and exit codes."""

import pytest

import main as cli


@pytest.fixture
def cli_db(monkeypatch, tmp_path):
    """Point every CLI command at a throwaway database."""
    url = f"sqlite:///{(tmp_path / 'cli.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    from src.config import reset_settings

    reset_settings()
    return url


# ------------------------------------------------------------------ parsing
def test_customer_ids_are_parsed_and_deduplicated():
    assert cli._parse_customer_ids(" 3, 1 ,3,2 ") == [3, 1, 2]


def test_empty_customer_ids_are_an_empty_list():
    assert cli._parse_customer_ids("") == []
    assert cli._parse_customer_ids(None) == []
    assert cli._parse_customer_ids(",, ,") == []


@pytest.mark.parametrize("raw", ["abc", "1,two", "1;2", "1.5"])
def test_invalid_customer_ids_stop_the_run(raw):
    with pytest.raises(SystemExit):
        cli._parse_customer_ids(raw)


@pytest.mark.parametrize("raw", ["0", "-3"])
def test_customer_ids_must_be_positive(raw):
    with pytest.raises(SystemExit):
        cli._parse_customer_ids(raw)


@pytest.mark.parametrize("raw", ["0", "-1", "abc", "", "2.5"])
def test_positive_int_rejects_nonsense(raw):
    import argparse

    with pytest.raises(argparse.ArgumentTypeError):
        cli._positive_int(raw)


def test_positive_int_accepts_valid_values():
    assert cli._positive_int("7") == 7


@pytest.mark.parametrize(
    "argv",
    [
        ["run", "--limit", "0"],
        ["run", "--days", "-1"],
        ["seed", "--customers", "0"],
        ["customers", "--limit", "x"],
        ["report", "--campaign", "0"],
    ],
)
def test_out_of_range_options_are_rejected_before_anything_runs(argv):
    with pytest.raises(SystemExit) as excinfo:
        cli.build_parser().parse_args(argv)
    assert excinfo.value.code == 2


# ------------------------------------------------------------------ commands
def test_no_command_prints_help(capsys):
    assert cli.main([]) == 0
    assert "usage" in capsys.readouterr().out


def test_config_command_reports_simulated_integrations(capsys):
    assert cli.main(["config"]) == 0
    out = capsys.readouterr().out
    assert "dry run:       True" in out
    assert "simulated:" in out


def test_seed_then_list_then_run(cli_db, capsys):
    assert cli.main(["seed", "--customers", "2"]) == 0
    assert cli.main(["customers"]) == 0
    listed = capsys.readouterr().out
    assert "john.smith@techcorp.example" in listed

    assert cli.main(["run", "--campaign", "cli-test"]) == 0
    ran = capsys.readouterr().out
    assert "Outreach campaign completed" in ran
    assert "Emails sent:        2" in ran

    assert cli.main(["report", "--campaign", "1"]) == 0
    assert "call_success_rate" in capsys.readouterr().out


def test_run_without_customers_reports_the_seed_hint(cli_db, capsys):
    assert cli.main(["init-db"]) == 0
    capsys.readouterr()
    assert cli.main(["run"]) == 1
    assert "Seed the database" in capsys.readouterr().out


def test_report_without_metrics_exits_nonzero(cli_db, capsys):
    assert cli.main(["init-db"]) == 0
    capsys.readouterr()
    assert cli.main(["report"]) == 1
    assert "No metrics recorded" in capsys.readouterr().out


def test_report_for_an_unknown_campaign_exits_nonzero(cli_db, capsys):
    assert cli.main(["init-db"]) == 0
    capsys.readouterr()
    assert cli.main(["report", "--campaign", "42"]) == 1
    assert "not found" in capsys.readouterr().out


def _parser_running(func):
    """A one-command parser whose command body is `func`."""
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_subparsers(dest="command").add_parser("boom").set_defaults(func=func)
    return parser


def test_unexpected_errors_are_reported_not_raised(monkeypatch, capsys):
    def explode(args):
        raise RuntimeError("database is on fire")

    monkeypatch.setattr(cli, "build_parser", lambda: _parser_running(explode))
    assert cli.main(["boom"]) == 1
    assert "database is on fire" in capsys.readouterr().out


def test_keyboard_interrupt_exits_with_130(monkeypatch, capsys):
    def interrupt(args):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "build_parser", lambda: _parser_running(interrupt))
    assert cli.main(["boom"]) == 130
    assert "Interrupted" in capsys.readouterr().out
