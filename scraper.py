import requests
from bs4 import BeautifulSoup
import config


def get_soup(path):
    """
    Downloads one page from the Bellhaven website and parses it into a
    BeautifulSoup object we can search through, like a queryable version
    of the HTML.
    """
    url = f"{config.WEBSITE_BASE}{path}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")

def parse_card(card):
    """
    Given one BeautifulSoup 'card' element, pulls out the name, url slug,
    city, state, and care offering badges.
    """
    link = card.select_one("h3 a")
    name = link.text.strip()
    href = link["href"]  # e.g. "/communities/bellhaven-of-maplewood"

    city_div = card.select_one(".city")
    city_state_text = city_div.text.strip() if city_div else ""
    if "," in city_state_text:
        city, state = city_state_text.rsplit(",", 1)
        city, state = city.strip(), state.strip()
    else:
        city, state = city_state_text, ""

    badges = [b.text.strip() for b in card.select(".badge")]

    return {
        "name": name,
        "url": f"{config.WEBSITE_BASE}{href}",
        "city": city,
        "state": state,
        "care_offerings": badges,
    }


def has_next_page(soup):
    """Checks the pager for a 'Next' link. Returns True/False."""
    pager = soup.select_one(".pager")
    if not pager:
        return False
    for link in pager.select("a"):
        if "next" in link.text.strip().lower():
            return True
    return False


def scrape_all_communities():
    """
    Walks every page of /communities, parsing every card, until there's no
    'Next' link left. Returns a list of location dicts.
    """
    locations = []
    page = 1

    while True:
        path = "/communities" if page == 1 else f"/communities?page={page}"
        soup = get_soup(path)
        cards = soup.select(".card")

        for card in cards:
            locations.append(parse_card(card))

        if not has_next_page(soup):
            break
        page += 1

    return locations

def parse_detail_page(url):
    """
    Visits one community's detail page and extracts the street address and
    zip code from the <dl class="detail"> block. The address <dd> contains
    two lines separated by a <br/> tag: street on line 1, "City, ST ZIP" on
    line 2.
    """
    path = url.replace(config.WEBSITE_BASE, "")
    soup = get_soup(path)

    address_dt = None
    for dt in soup.select(".detail dt"):
        if dt.text.strip().lower() == "address":
            address_dt = dt
            break

    if not address_dt:
        return {"street": "", "zip": ""}

    address_dd = address_dt.find_next_sibling("dd")
    # get_text(separator="|") turns the <br/>-separated lines into a string
    # like "210 Orchard Lane|Maplewood, OH 44280", which we can split cleanly
    lines = address_dd.get_text(separator="|").split("|")
    street = lines[0].strip() if len(lines) > 0 else ""
    city_state_zip = lines[1].strip() if len(lines) > 1 else ""

    # city_state_zip looks like "Maplewood, OH 44280" - zip is the last token
    zip_code = city_state_zip.split()[-1] if city_state_zip else ""

    return {"street": street, "zip": zip_code}


def scrape_all_locations():
    """
    Full scrape: gets the list of all communities, then visits each one's
    detail page to fill in street address and zip. Returns a list of
    complete location dicts ready for matching against the CRM.
    """
    locations = scrape_all_communities()

    for loc in locations:
        detail = parse_detail_page(loc["url"])
        loc["street"] = detail["street"]
        loc["zip"] = detail["zip"]

    return locations