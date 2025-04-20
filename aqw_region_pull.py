import time
import requests
import json
from tqdm import tqdm
from bs4 import BeautifulSoup


# retrieves list of regions 
def get_region_dict(region_url="http://aqwwiki.wikidot.com/locations", sleep_duration=1):
    time.sleep(sleep_duration)
    res = requests.get(region_url)
    map_site = BeautifulSoup(res.text, "html.parser")
    map_site_content = map_site.find("div", id="page-content")
    region_dict = {}
    for a in map_site_content.find("p").find_all("a"):
        region_dict[a.get_text()] = a["href"][1:]
    return region_dict


# retrieves list of locations in each region
def get_loc_in_regions(region, sleep_duration=1):
    time.sleep(sleep_duration)
    res = requests.get(f"http://aqwwiki.wikidot.com/{region}")
    map_site = BeautifulSoup(res.text, "html.parser")
    map_site_content = map_site.find("div", id="page-content")
    links = []
    for a in map_site_content.find_all("a"):
        try:
            if "/" in a["href"]:
                links.append(a["href"][1:])
        except:
            pass
    return list(set(links))


# returns map of regions to lists of locations
def get_region_to_loc_dict(region_url="http://aqwwiki.wikidot.com/locations"):
    region_dict = get_region_dict(region_url)
    region_to_loc_dict = {}
    for k, v in tqdm(region_dict.items()):
        try:
            region_to_loc_dict[k] = get_loc_in_regions(v)
        except:
            print(f"ERROR: Region {k}")
    return region_to_loc_dict


def main():
    save_loc = "region_map.json"
    region_to_loc_dict = get_region_to_loc_dict()
    with open(save_loc, "w") as f:
        json.dump(region_to_loc_dict, f, indent=4)


if __name__ == "__main__":
    main()