from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
import json

from schemas.schemas import TrialExtraction

DATA_FILE = Path(__file__).parent.parent / "data" / "extractions.json"

load_dotenv()  # loads OPENAI_API_KEY from .env

client = OpenAI()

prompt = (Path(__file__).parent / "prompt.txt").read_text()


def extract_agent(unstructured_text: str) -> TrialExtraction | None:
    response = client.responses.parse(
        model="gpt-6-luna",
        instructions=prompt,        # rules live here
        input=unstructured_text,    # user data stays separate
        text_format=TrialExtraction,
    )
    return response.output_parsed

def save_extracted_data(json_obj: TrialExtraction, path: Path = DATA_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    records = []
    if path.exists() and path.stat().st_size > 0:
        with path.open("r", encoding="utf-8") as f:
            records = json.load(f)

    records.append(json_obj.model_dump())

    with path.open("w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)