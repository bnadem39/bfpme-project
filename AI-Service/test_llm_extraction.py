"""Execute l'extraction LLM et produit JSON + PDF pour controle."""

import argparse
import json
from pathlib import Path

from app.extraction.llm_extractor import extract_with_llm
from app.extraction.pdf_report import create_extraction_pdf


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("text", nargs="?", default="output/002.txt")
    parser.add_argument("--model", default="local-model")
    args = parser.parse_args()

    source = Path(args.text)
    text = source.read_text(encoding="utf-8")
    result = extract_with_llm(text, model=args.model)

    output_dir = Path("output/pdf")
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{source.stem}_extraction.json"
    pdf_path = output_dir / f"{source.stem}_extraction.pdf"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    create_extraction_pdf(result, str(pdf_path))

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print(f"JSON: {json_path.resolve()}")
    print(f"PDF : {pdf_path.resolve()}")


if __name__ == "__main__":
    main()
