"""Print the deduplicated effect glossary, most-repeated effect first."""
import glossary


def main():
    entries = sorted(glossary.load_glossary(), key=lambda e: -e["occurrence_count"])
    for e in entries:
        authored = "authored" if e.get("plain_text") else "UNAUTHORED"
        print("%2d  %-10s  %-8s  %s" % (
            e["occurrence_count"], e["effect_id"], authored, e["raw_text"]))
        print("    cards: %s" % ", ".join(e["card_ids"]))

    total_extractions = sum(e["occurrence_count"] for e in entries)
    print("\n%d unique effects, %d total occurrences across cards"
          % (len(entries), total_extractions))


if __name__ == "__main__":
    main()
