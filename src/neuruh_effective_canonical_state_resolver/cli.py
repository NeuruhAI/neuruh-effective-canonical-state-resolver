import argparse, json
from pathlib import Path
from .core import EffectiveCanonicalResolution, resolve

def main(argv=None):
    p = argparse.ArgumentParser(prog="neuruh-effective-canonical-state-resolver")
    s = p.add_subparsers(dest="cmd", required=True)
    for n in ("resolve", "validate", "digest"):
        x = s.add_parser(n)
        x.add_argument("file")
    a = p.parse_args(argv)
    raw = json.loads(Path(a.file).read_text())
    if a.cmd == "resolve":
        r = resolve(
            target_id=raw["target_id"],
            lifecycle_tips=raw.get("lifecycle_tips", []),
            revision_lineages=raw.get("revision_lineages", []),
        )
        print(json.dumps(r.to_dict(), indent=2, sort_keys=True))
    else:
        r = EffectiveCanonicalResolution.from_mapping(raw)
        if a.cmd == "validate":
            print(json.dumps({
                "ok": True,
                "resolution_status": r.resolution_status,
                "reason_code": r.reason_code,
                "effective_source": r.effective_source,
                "effective_stage": r.effective_stage,
                "effective_state_digest": r.effective_state_digest,
                "mutation_authority": False,
            }, sort_keys=True))
        else:
            print(r.resolution_digest)

if __name__ == "__main__":
    main()
