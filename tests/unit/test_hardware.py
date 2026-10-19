from kurooto.core.hardware import GPU, Machine, profile, recommend


def machine(os="windows", arch="amd64", ram=16.0, gpus=(), battery=True, on_ac=True):
    return Machine(
        os=os,
        os_version="11",
        arch=arch,
        cpu="Test CPU",
        cores=8,
        threads=16,
        ram_gb=ram,
        gpus=list(gpus),
        disk_free_gb=100,
        battery=battery,
        on_ac=on_ac,
    )


def tags(m):
    return [x["tag"] for x in recommend(m).local_models]


def test_a_4gb_laptop_gpu():
    m = machine(gpus=[GPU("NVIDIA GeForce RTX 3050 Laptop GPU", 4.0, "nvidia"), GPU("AMD Radeon", None, "amd")])
    r = recommend(m)
    assert r.profile == "small-gpu" and r.embeddings == "ollama"
    assert tags(m) == ["nomic-embed-text", "qwen3:4b-instruct-2507-q4_K_M"]
    assert sum(x["size_gb"] for x in r.local_models) < 3.5
    assert any("7B" in n for n in r.notes)


def test_no_gpu_laptops_get_nothing_local():
    galaxy_book = machine(gpus=[GPU("Intel(R) Iris(R) Xe Graphics", None, "intel")])
    intel_mac = machine(os="macos", arch="x86_64", gpus=[GPU("Intel Iris Plus", 1.5, "intel")])
    for m in (galaxy_book, intel_mac):
        r = recommend(m)
        assert r.profile == "light" and r.local_models == [] and r.embeddings == "gemini" and r.reduced_motion


def test_apple_silicon():
    assert profile(machine(os="macos", arch="arm64", ram=16)) == "apple"
    assert tags(machine(os="macos", arch="arm64", ram=8)) == ["nomic-embed-text"]


def test_big_cards_and_low_memory():
    assert tags(machine(gpus=[GPU("RTX 4060", 8.0, "nvidia")])) == ["nomic-embed-text", "gemma4:e4b"]
    assert profile(machine(gpus=[GPU("RTX 4070 Ti", 12.0, "nvidia")])) == "big-gpu-12"
    assert profile(machine(ram=4, gpus=[GPU("RTX 3050", 4.0, "nvidia")])) == "light"
    assert profile(machine(gpus=[GPU("GT 1030", 2.0, "nvidia")])) == "light"


def test_battery_note():
    assert any("battery" in n for n in recommend(machine(on_ac=False)).notes)
    assert not any("battery" in n for n in recommend(machine(battery=False, on_ac=None)).notes)
