from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PIL = pytest.importorskip("PIL")


def test_render_writes_an_animated_gif(tmp_path):
    from PIL import Image

    from scripts.make_demo_gif import render

    out = tmp_path / "demo.gif"
    render(["How long is the free trial?"], out, ROOT / "config.yaml")
    with Image.open(out) as gif:
        assert gif.format == "GIF"
        assert gif.n_frames > 10


def test_failing_command_raises_with_its_message(tmp_path):
    from scripts.make_demo_gif import render

    with pytest.raises(SystemExit, match="Record workflow"):
        render(
            ["A question nobody has recorded about Lumen+ refunds?"], tmp_path / "x.gif", ROOT / "config.yaml"
        )
    assert not (tmp_path / "x.gif").exists()
