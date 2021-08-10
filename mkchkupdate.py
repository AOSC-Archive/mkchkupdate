#!/usr/bin/python3

import os
import sys
import httpx
import threading
import queue

q = queue.Queue()


def make_no_chkupdate_list(directory_name: str) -> list:
    result = []
    with os.scandir(directory_name) as dir1:
        for section in dir1:
            if section.is_dir() and not section.name.startswith('.'):
                with open("{}/{}/spec".format(directory_name, section.name)) as f:
                    spec = f.readlines()
                    if len([i for i in spec if "CHKUPDATE=" in i]) == 0:
                        result.append(section.name)
    return result


def request_anitya(package_name: str) -> dict:
    r = httpx.get(
        "https://release-monitoring.org/api/projects/?pattern={}".format(package_name))
    r.raise_for_status()
    return r.json()


def make_result(no_chkupdate_list: list) -> dict:
    for i in no_chkupdate_list:
        try:
            anitya_json = request_anitya(i)
        except Exception as e:
            print(e)
        anitya_items = []
        if anitya_json["total"] != 0:
            for j in anitya_json["projects"]:
                d = {
                    "Name": j["name"],
                    "Homepage": j["homepage"],
                    "LastestVersion": j["stable_versions"][0] if len(j["stable_versions"]) != 0 else "None",
                    "CHKUPDATE": "CHKUPDATE=\"anitya::id={}\"".format(j["id"])
                }
                anitya_items.append(d)
        github_or_gitlab_source = get_github_or_gitlab_source(i)
        q.put({'name': i, 'anitya': anitya_items,
               'github/gitlab': github_or_gitlab_source})
    q.put(None)


def get_github_or_gitlab_source(package_name: str) -> str:
    path = search_package_path(package_name)
    if path is None:
        return ""
    with open("{}/spec".format(path)) as f:
        spec = f.readlines()
        srcs = []
        result = ""
        for i in spec:
            if "SRCS=" in i:
                if len(i.split("::")) > 1:
                    srcs += i.split("::")[1][:-1].split('\n')
                else:
                    srcs += i[:-1].split('\n')
        for i in srcs:
            src_split = i.split("/")
            if 'github' in i:
                result = "CHKUPDATE=\"github::repo={}/{}\"".format(
                    src_split[3], src_split[4])
            elif 'gitlab' in i:
                result = "CHKUPDATE=\"gitlab::repo={}/{}\"".format(
                    src_split[3], src_split[4])

        return result


def get_result_to_user(directory_name: str):
    no_chkupdate_list = make_no_chkupdate_list(directory_name)
    t = threading.Thread(target=make_result, args=(no_chkupdate_list, ))
    t.start()
    while True:
        result = q.get()
        if result is None:
            return
        print("Name: {}".format(result["name"]))
        print("Anitya: ")
        d = {}
        for index, anitya_item in enumerate(result["anitya"]):
            print("1-{}. Name: {}, Homepage: {}, Lastest Version: {}, CHKUPDATE: {}".format(
                index+1, anitya_item["Name"], anitya_item["Homepage"], anitya_item["LastestVersion"], anitya_item["CHKUPDATE"]))
            d["1-{}".format(index+1)] = anitya_item["CHKUPDATE"]
        print("2. Github/Gitlab: {}".format(result["github/gitlab"]))
        d["2"] = result["github/gitlab"]
        ipt = input("CHKUPDATE?: ")
        set_chkupdate(result["name"], d.get(ipt) or ipt)


def set_chkupdate(package_name: str, chkupdate: str):
    path = search_package_path(package_name)
    if path is None:
        return
    try:
        with open("{}/spec".format(path), "at") as f:
            f.write("{}\n".format(chkupdate))
    except Exception as e:
        print(e)


def search_package_path(package_name: str) -> str:
    with os.scandir(".") as dir1:
        for section in dir1:
            if section.is_dir() and not section.name.startswith('.'):
                with os.scandir(section) as dir2:
                    for package in dir2:
                        if package.name == package_name and package.is_dir() and os.path.isdir(
                                os.path.join(package, "autobuild")):
                            return package.path[2:]
                        # search subpackage, like arch-install-scripts/01-genfstab
                        path = package
                        if os.path.isdir(path) and section.name != "groups":
                            with os.scandir(path) as dir3:
                                for subpackage in dir3:
                                    if subpackage.name != "autobuild" and subpackage.is_dir():
                                        try:
                                            with open(os.path.join(subpackage, "defines"), "r") as f:
                                                defines = f.readlines()
                                        except:
                                            with open(os.path.join(subpackage, "autobuild/defines"), "r") as f:
                                                defines = f.readlines()
                                        finally:
                                            for line in defines:
                                                if "PKGNAME=" in line and package_name in line:
                                                    return package.path[2:]


if __name__ == "__main__":
    get_result_to_user(sys.argv[1])
