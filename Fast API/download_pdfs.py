from pathlib import Path
import time
import requests
import xml.etree.ElementTree as ET

# Set data directory relative to script location
CURRENT_DIR = Path(__file__).resolve().parent
DATA_DIR = CURRENT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

API_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
PDF_URL = "https://europepmc.org/articles/{pmcid}?pdf=render"

TARGET = 50
QUERY = "OPEN_ACCESS:Y AND HAS_PDF:Y AND (clinical trial OR medicine)"

session = requests.Session()
session.headers.update({
    "User-Agent": "MedicalTrialExtractor/1.0 (educational project; mailto:student@example.org)",
    "Accept": "application/pdf,application/json,text/html,*/*",
})


def get_articles():
    response = session.get(
        API_URL,
        params={
            "query": QUERY,
            "format": "json",
            "pageSize": 200,
            "resultType": "core",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()["resultList"]["result"]


def download_pdf(article):
    pmcid = article.get("pmcid")
    if not pmcid:
        return False

    output_path = DATA_DIR / f"{pmcid}.pdf"
    if output_path.exists() and output_path.stat().st_size > 0:
        print(f"Already exists: {output_path.name}")
        return True

    url = PDF_URL.format(pmcid=pmcid)

    try:
        response = session.get(url, timeout=60)
        response.raise_for_status()

        # Confirm that the response is a PDF, not an HTML page.
        if not response.content.startswith(b"%PDF-"):
            print(f"Skipped (not a PDF): {pmcid}")
            return False

        output_path.write_bytes(response.content)
        print(f"Downloaded: {output_path.name} — {article.get('title', '')[:70]}")
        return True

    except requests.RequestException as exc:
        print(f"Failed: {pmcid}: {exc}")
        return False


def download_from_arxiv_fallback(needed: int) -> int:
    """Fallback to direct open-access arXiv clinical trial / medical papers

    if Europe PMC web URLs block automated requests with Cloudflare challenges.
    """
    print(f"\n[Fallback] Europe PMC rendered URLs are subject to Cloudflare challenges.")
    print(f"[Fallback] Fetching {needed} open-access clinical trial papers from arXiv API...")

    arxiv_api = (
        f"https://export.arxiv.org/api/query?search_query=all:%22clinical+trial%22+OR+cat:q-bio.QM"
        f"&start=0&max_results={max(needed * 2, 50)}"
    )

    try:
        resp = session.get(arxiv_api, timeout=30)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        downloaded = 0
        for entry in root.findall("atom:entry", ns):
            if downloaded >= needed:
                break

            title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
            id_url = entry.find("atom:id", ns).text.strip()
            paper_id = id_url.split("/abs/")[-1].replace("/", "_")

            pdf_link = entry.find("atom:link[@title='pdf']", ns)
            if pdf_link is None:
                continue

            pdf_url = pdf_link.attrib["href"]
            output_path = DATA_DIR / f"arxiv_{paper_id}.pdf"

            if output_path.exists() and output_path.stat().st_size > 0:
                print(f"Already exists: {output_path.name}")
                downloaded += 1
                continue

            try:
                pdf_resp = session.get(pdf_url, timeout=60)
                if pdf_resp.content.startswith(b"%PDF-"):
                    output_path.write_bytes(pdf_resp.content)
                    print(f"Downloaded (arXiv): {output_path.name} — {title[:70]}")
                    downloaded += 1
                    time.sleep(0.5)
                else:
                    print(f"Skipped non-PDF for {paper_id}")
            except Exception as e:
                print(f"Failed {paper_id}: {e}")

        return downloaded
    except Exception as exc:
        print(f"arXiv fallback failed: {exc}")
        return 0


def main():
    print(f"Searching Europe PMC for open-access papers (target: {TARGET})...")
    articles = get_articles()
    print(f"Found {len(articles)} candidate articles. Starting download...")
    downloaded = 0
    europe_pmc_blocked = 0

    for article in articles:
        if download_pdf(article):
            downloaded += 1
        else:
            europe_pmc_blocked += 1

        if downloaded >= TARGET:
            break

        # If Europe PMC consistently returns 403 (Cloudflare challenge on /articles/... endpoint),
        # automatically fall back to open-access clinical trial papers.
        if europe_pmc_blocked >= 5 and downloaded == 0:
            print("\nNotice: Europe PMC web render endpoints are currently blocked by bot mitigation.")
            fallback_count = download_from_arxiv_fallback(TARGET - downloaded)
            downloaded += fallback_count
            break

        time.sleep(0.5)

    print(f"\nFinished: {downloaded}/{TARGET} PDFs saved in {DATA_DIR.resolve()}")

    if downloaded < TARGET:
        print("Run again or broaden QUERY to find more eligible papers.")


if __name__ == "__main__":
    main()
