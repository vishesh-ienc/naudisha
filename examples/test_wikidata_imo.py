"""
Test diverse IMO queries via Wikidata SPARQL.
"""

import json
import urllib.parse
import urllib.request


def query_wikidata_by_imo(imo: str):
    sparql = f"""
    SELECT ?ship ?shipLabel ?typeLabel ?loa ?beam ?draft WHERE {{
      ?ship wdt:P458 "{imo}".
      OPTIONAL {{ ?ship wdt:P31 ?type. }}
      OPTIONAL {{ ?ship wdt:P2043 ?loa. }}
      OPTIONAL {{ ?ship wdt:P2261 ?beam. }}
      OPTIONAL {{ ?ship wdt:P2262 ?draft. }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    LIMIT 1
    """
    url = "https://query.wikidata.org/sparql?query=" + urllib.parse.quote(sparql) + "&format=json"
    req = urllib.request.Request(url, headers={"User-Agent": "NauDisha-Maritime-API/1.0 (https://github.com/vishesh-ienc/naudisha)"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            bindings = data.get("results", {}).get("bindings", [])
            print(f"[Wikidata] Results for {imo}: {len(bindings)}")
            if bindings:
                b = bindings[0]
                name = b.get("shipLabel", {}).get("value")
                stype = b.get("typeLabel", {}).get("value")
                loa = b.get("loa", {}).get("value")
                beam = b.get("beam", {}).get("value")
                draft = b.get("draft", {}).get("value")
                print(f"   Name: {name}, Type: {stype}, LOA: {loa}, Beam: {beam}, Draft: {draft}")
                return {"name": name, "type": stype, "loa": loa, "beam": beam, "draft": draft}
            return None
    except Exception as e:
        print(f"[Wikidata] Error for {imo}: {e}")
        return None


def main():
    imos = ["9176187", "9748289", "9703291", "9443413", "9241061", "9499890", "9074729"]
    for imo in imos:
        query_wikidata_by_imo(imo)


if __name__ == "__main__":
    main()
