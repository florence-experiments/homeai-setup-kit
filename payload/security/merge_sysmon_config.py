"""Merges sysmon-override.xml into the sysmon-modular sysmonconfig.xml.

Usage: python merge_sysmon_config.py sysmonconfig.xml sysmon-override.xml sysmonconfig-merged.xml
Copies each <RuleGroup> from the override into <EventFiltering>. Re-running is safe: groups whose
name already exists are replaced, not duplicated. Standard library only."""
import sys
import xml.etree.ElementTree as ET


def merge(base_path, override_path, out_path):
    base = ET.parse(base_path)
    root = base.getroot()
    if root.tag != "Sysmon":
        raise SystemExit("not a Sysmon config: " + base_path)
    ef = root.find("EventFiltering")
    if ef is None:
        ef = ET.SubElement(root, "EventFiltering")
    groups = ET.parse(override_path).getroot().findall("RuleGroup")
    names = {g.get("name") for g in groups}
    for old in [g for g in ef.findall("RuleGroup") if g.get("name") in names]:
        ef.remove(old)
    for g in groups:
        ef.append(g)
    base.write(out_path, encoding="utf-8", xml_declaration=False)
    return len(groups)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(__doc__)
    n = merge(*sys.argv[1:])
    print("merged %d rule groups into %s" % (n, sys.argv[3]))
