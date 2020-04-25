#!/usr/bin/env python3

# divide.py is a simple python script suggesting ways to divide the
# parts of your Lego set into categories.
#
# Copyright (C) 2020  Luuk Berkers <berkers.luuk@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import colorama
import json
import requests
from requests_oauthlib import OAuth1
import sys
import urllib.request

if len(sys.argv) != 3:
    print("Usage: divide <set_number> <divisions>")
    sys.exit(1)
else:
    pass


def log(s=str(), *, only_console=False, always_console=False):
    console_mode = True
    if console_mode or always_console:
        print(s)
    elif not only_console:
        with open("logs", "a") as log_file:
            log_file.write(s + "\n")


log(
    "divide.py  Copyright (C) 2020  Luuk Berkers <berkers.luuk@gmail.com>\n\n"
    "This program comes with ABSOLUTELY NO WARRANTY.\n"
    "This is free software, and you are welcome to redistribute it\n"
    "under certain conditions. See LICENSE for details.\n",
    only_console=True,
)

colorama.init(autoreset=True)

SET_NUM = sys.argv[1]
DIVISIONS = int(sys.argv[2])

BL_CACHE = "bricklink_weight_cache.json"
CAT_FILE = "rebrickable_part_categories.json"
MAX_CAT_NUM = 67 + 1  # + 1 because this is used as List length

REBRICKABLE_API = "https://rebrickable.com/api/v3/lego/"
BL_API = "https://api.bricklink.com/api/store/v1/"

with open("keys.json", "r") as key_file:
    KEYS = json.loads(key_file.read())


def find_index(list, key, val):
    for i in range(len(list)):
        if list[i][key] == val:
            return i
    return "key:value pair does not exist in list"


class Part:
    def __init__(self, num, name, quantity, total_weight, cat_id, super_cat, standard):
        self.num = num
        self.name = name
        self.quantity = quantity
        self.total_weight = total_weight
        self.cat_id = cat_id
        self.super_cat = super_cat
        self.standard = standard
        self.used = False


def get_weight(bl_part_num):
    try:
        with open(BL_CACHE, "r") as cache_file:
            weight_data = json.loads(cache_file.read())
    except FileNotFoundError:
        weight_data = dict()

    weight = str()
    if bl_part_num in weight_data:
        weight = weight_data[bl_part_num]
    else:
        url = BL_API + "items/part/" + bl_part_num
        # Order is not actually guarantied here so this might not work forever
        auth = OAuth1(*KEYS["bricklink"].values())
        log("Requesting: " + url)
        weight = requests.get(url, auth=auth).json()["data"]["weight"]
        weight_data[bl_part_num] = weight
        with open(BL_CACHE, "w") as cache_file:
            json.dump(weight_data, cache_file, indent=2)

    return float(weight)


def process_data(data, accumulator):
    with open(CAT_FILE, "r") as category_file:
        categories = json.loads(category_file.read())["results"]
    for part in data["results"]:
        part_data = part["part"]
        cat_index = find_index(categories, "id", part_data["part_cat_id"])
        bl_num = (
            # Seems like the last in the list is usually the most recent one
            part_data["external_ids"]["BrickLink"][-1]
            if "BrickLink" in part_data["external_ids"]
            else part_data["part_num"]
        )
        accumulator.append(
            Part(
                part_data["part_num"],
                part_data["name"],
                part["quantity"],
                part["quantity"] * get_weight(bl_num),
                part_data["part_cat_id"],
                categories[cat_index]["super"],
                categories[cat_index]["standard"],
            )
        )

    return accumulator


def dedup_parts(parts):
    new_list = list()
    while len(parts) != 0:
        temp = parts.pop()
        same_parts = [p for p in parts if p.num == temp.num]
        for dup in same_parts:
            temp.quantity += dup.quantity
            temp.total_weight += dup.total_weight
            parts.remove(dup)
        new_list.append(temp)

    return new_list


def get_total_in_super_cat(parts):
    total = dict()
    for part in parts:
        if not part.used and not part.super_cat in total:
            total[part.super_cat] = part.total_weight
        elif not part.used:
            total[part.super_cat] += part.total_weight

    return total


def get_total_in_super_cat_S_N(parts, category_list):
    total = dict()
    for part in parts:
        if not part.used:
            index = find_index(category_list, "id", part.cat_id)
            standard = category_list[index]["standard"]
            super_cat_S_N = part.super_cat + (
                " Standard" if standard else " Non-Standard"
            )
            if not super_cat_S_N in total:
                total[super_cat_S_N] = part.total_weight
            else:
                total[super_cat_S_N] += part.total_weight

    return total


def get_total_in_cat(parts):
    total = [0] * MAX_CAT_NUM
    for part in parts:
        if not part.used:
            total[part.cat_id] += part.total_weight

    return total


def use_super_cat(parts, id):
    count = 0
    for part in [p for p in parts if p.super_cat == id and not p.used]:
        part.used = True
        count += part.total_weight
    return count


def use_super_cat_S_N(parts, id):
    assert id.endswith("Standard"), "id should end with 'Standard' or 'Non-Standard'"
    standard = not id.endswith("Non-Standard")
    super_cat = id[:-9] if standard else id[:-13]
    count = 0
    for part in [
        p
        for p in parts
        if p.super_cat == super_cat and p.standard == standard and not p.used
    ]:
        part.used = True
        count += part.total_weight
    return count


def use_part(parts, id):
    count = 0
    for part in [p for p in parts if p.num == id and not p.used]:
        part.used = True
        count += part.total_weight
    return count


def use_cat(parts, id):
    count = 0
    for part in [p for p in parts if p.cat_id == id and not p.used]:
        part.used = True
        count += part.total_weight
    return count


def use_grand_total(parts, id):
    count = 0
    for part in [p for p in parts if not p.used]:
        part.used = True
        count += part.total_weight
    return count


def divide_parts(parts, category_list):
    # grand_total = sum([p.quantity for p in parts if not p.used])
    grand_total = sum([p.total_weight for p in parts if not p.used])
    groupings = dict()
    log(
        "\nTotal weight: "
        + colorama.Fore.YELLOW
        + "{:.2f}".format(grand_total)
        + colorama.Fore.RESET
        + " grams",
        only_console=True,
    )

    # ppd = grand_total // DIVISIONS
    wpd = grand_total / DIVISIONS

    log(
        "About "
        + colorama.Fore.YELLOW
        + "{:.2f}".format(wpd)
        + colorama.Fore.RESET
        + " grams per division",
        only_console=True,
    )

    while grand_total != 0:
        total_in_super_cat = get_total_in_super_cat(parts)

        # log('\nSupercategory totals:', only_console=True)
        # for super_cat, quantity in total_in_super_cat.items():
        #     log(super_cat + ': ' + colorama.Fore.YELLOW + str(quantity), only_console=True)

        total_in_super_cat_S_N = get_total_in_super_cat_S_N(parts, category_list)

        # log('\nSupercategory Standard/Non-Standard totals:', only_console=True)
        # for super_cat_S_N, quantity in total_in_super_cat_S_N.items():
        #     log(super_cat_S_N + ': ' + colorama.Fore.YELLOW + str(quantity), only_console=True)

        total_in_cat = get_total_in_cat(parts)

        # log('\nCategory totals:', only_console=True
        # for cat_num in range(MAX_CAT_NUM):
        #     if total_in_cat[cat_num] != 0:
        #         index = find_index(category_list, 'id', cat_num)
        #         log(
        #             category_list[index]['name']
        #             + ': '
        #             + colorama.Fore.YELLOW
        #             + str(total_in_cat[cat_num]),
        #             only_console=True,
        #         )

        # log('\nPart totals:', only_console=True)
        # for part in [p for p in parts if not p.used]:
        # log(part.name + ': ' + colorama.Fore.YELLOW + str(part.quantity), only_console=True)

        best_part = {"id": None, "name": None, "delta": None}
        for part in [p for p in parts if not p.used]:
            delta = abs(wpd - part.total_weight)
            if (
                best_part["delta"] == None
                or best_part["delta"] > delta
                or (
                    best_part["delta"] == delta
                    and len(part.name) < len(best_part["name"])
                )
            ):
                best_part = {"id": part.num, "name": part.name, "delta": delta}

        # log(
        #     "\nBest part: " + best_part["name"] + "\nDelta: " + str(best_part["delta"]), only_console=True
        # )

        best_cat = {"id": None, "name": None, "delta": None}
        for cat_num in range(MAX_CAT_NUM):
            if total_in_cat[cat_num] != 0:
                delta = abs(wpd - total_in_cat[cat_num])
                index = find_index(category_list, "id", cat_num)
                if (
                    best_cat["delta"] == None
                    or best_cat["delta"] > delta
                    or (
                        best_cat["delta"] == delta
                        and len(category_list[index]["name"]) < len(best_cat["name"])
                    )
                ):
                    best_cat = {
                        "id": cat_num,
                        "name": category_list[index]["name"],
                        "delta": delta,
                    }

        # log(
        #     "\nBest category: "
        #     + best_cat["name"]
        #     + "\nDelta: "
        #     + str(best_cat["delta"]),
        #     only_console=True,
        # )

        best_super_cat_S_N = {"id": None, "name": None, "delta": None}
        for super_cat_S_N, total_weight in total_in_super_cat_S_N.items():
            delta = abs(wpd - total_weight)
            if (
                best_super_cat_S_N["delta"] == None
                or best_super_cat_S_N["delta"] > delta
                or (
                    best_super_cat_S_N["delta"] == delta
                    and len(super_cat_S_N) < len(best_super_cat_S_N["name"])
                )
            ):
                best_super_cat_S_N = {
                    "id": super_cat_S_N,
                    "name": super_cat_S_N,
                    "delta": delta,
                }

        # log(
        #     "\nBest supercategory standard/non-standard: "
        #     + best_super_cat_S_N["name"]
        #     + "\nDelta: "
        #     + str(best_super_cat_S_N["delta"]),
        #     only_console=True,
        # )

        best_super_cat = {"id": None, "name": None, "delta": None}
        for super_cat, total_weight in total_in_super_cat.items():
            delta = abs(wpd - total_weight)
            if (
                best_super_cat["delta"] == None
                or best_super_cat["delta"] > delta
                or (
                    best_super_cat["delta"] == delta
                    and len(super_cat) < len(best_super_cat["name"])
                )
            ):
                best_super_cat = {"id": super_cat, "name": super_cat, "delta": delta}

        # log(
        #     "\nBest supercategory: "
        #     + best_super_cat["name"]
        #     + "\nDelta: "
        #     + str(best_super_cat["delta"]),
        #     only_console=True,
        # )

        grand_total_delta = abs(wpd - grand_total)
        # log("\nGrand total delta: " + str(grand_total_delta), only_console=True)

        bests = {
            "grand_total": {
                "id": "grand_total",
                "name": "All other parts",
                "delta": grand_total_delta,
            },
            "super_cat": best_super_cat,
            "cat": best_cat,
            "super_cat_S_N": best_super_cat_S_N,
            "part": best_part,
        }

        bests = {
            k: v for k, v in sorted(bests.items(), key=lambda best: best[1]["delta"])
        }

        use_functions = {
            "grand_total": use_grand_total,
            "super_cat": use_super_cat,
            "super_cat_S_N": use_super_cat_S_N,
            "cat": use_cat,
            "part": use_part,
        }
        best_key = list(bests.keys())[0]
        parts_used = use_functions[best_key](parts, bests[best_key]["id"])
        groupings[
            colorama.Fore.BLUE
            + best_key
            + ": "
            + colorama.Fore.LIGHTBLUE_EX
            + bests[best_key]["name"]
        ] = parts_used

        grand_total = sum([p.total_weight for p in parts if not p.used])

    return groupings


def main():
    url = REBRICKABLE_API + "sets/" + SET_NUM + "/?key=" + KEYS["rebrickable"]
    log("Requesting: " + url)
    raw_set_data = urllib.request.urlopen(url).read().decode()
    set_data = json.loads(raw_set_data)

    next_url = (
        REBRICKABLE_API + "sets/" + SET_NUM + "/parts/?key=" + KEYS["rebrickable"]
    )
    parts = list()

    while not next_url == None:
        log("Requesting: " + next_url)
        raw_data = urllib.request.urlopen(next_url).read().decode()
        data = json.loads(raw_data)
        parts = process_data(data, parts)
        next_url = data["next"]

    parts = dedup_parts(parts)

    log(
        "\nData for set "
        + colorama.Fore.CYAN
        + set_data["set_num"]
        + " "
        + colorama.Fore.BLUE
        + set_data["name"],
        only_console=True,
    )

    parts.sort(key=lambda p: p.total_weight)
    with open(CAT_FILE, "r") as category_file:
        categories = json.loads(category_file.read())
    groupings = divide_parts(parts, categories["results"])

    log(
        "\n"
        + colorama.Fore.YELLOW
        + str(len(groupings))
        + colorama.Fore.RESET
        + " groupings: ",
        only_console=True,
    )

    for group, amount in groupings.items():
        log(
            group + ": " + colorama.Fore.YELLOW + "{:.2f}".format(amount),
            only_console=True,
        )


if __name__ == "__main__":
    main()
    log()
