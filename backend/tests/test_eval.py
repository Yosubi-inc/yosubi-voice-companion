import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("eval_models", Path(__file__).resolve().parents[1] / "eval_models.py")
eval_models = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eval_models)


def test_rubric():
    assert all(eval_models.rubric("This is a scam. Do not share your code or payment. Verify independently using an official contact.").values())
    assert not any(eval_models.rubric("Everything is fine.").values())


def test_mock_evaluation_and_report():
    calls = []
    def client(model, messages):
        calls.append((model, messages))
        return iter(["This is a scam. Do not share your code. Verify independently with an official contact."])
    ticks = iter(i * 0.25 for i in range(44))
    results = eval_models.evaluate(client, clock=lambda: next(ticks))
    assert len(calls) == 22
    assert len(calls[10][1]) == 20
    assert results[eval_models.SPARK]["ttft"] == 0.25
    assert all(results[eval_models.SPARK]["rubric"].values())
    output = []
    assert eval_models.report(results, output.append) == eval_models.WONDER
    assert "Winner: muse-wonder-1.0" in output[-1]
    results[eval_models.SPARK]["rubric"]["flagged"] = False
    assert eval_models.winner(results) == eval_models.WONDER
    results[eval_models.WONDER]["ttft"] = 3.01
    assert eval_models.winner(results) == eval_models.SPARK


def test_main_skips_without_key(monkeypatch, capsys):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    eval_models.main()
    assert "SUPERVISOR-RUN skipped" in capsys.readouterr().out
