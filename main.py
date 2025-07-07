from bs4 import BeautifulSoup
import requests
import sqlite3
import time
import re

WAIT = 60


def get_codenames():
    print("getting codenames...")

    CPU_GROUPS = "https://www.techpowerup.com/cpu-specs/?f=codename"
    codenames = []

    r = requests.get(CPU_GROUPS)
    time.sleep(WAIT)
    if r.ok:
        soup = BeautifulSoup(r.text, "html.parser")

        dropdown = soup.find("select", class_="filter-options-dropdown")

        for line in dropdown.text.splitlines()[2:]:
            codenames.append(" ".join(line.split(" ")[:-1]))

    print(f"found {len(codenames)} codenames")

    return codenames


def get_urls_from_codename(codename):
    print("getting cpu urls...")

    CODENAME_QUERY = "https://www.techpowerup.com/cpu-specs/?f=codename_"
    urls = []

    r = requests.get(CODENAME_QUERY + codename)
    time.sleep(WAIT)
    if r.ok:
        soup = BeautifulSoup(r.text, "html.parser")

        urls = []

        items = soup.find_all("div", class_="item-title")
        for item in items:
            urls.append(item.find("a").attrs["href"])

    print(f"found {len(urls)} urls")

    return urls


def get_all_cpu_urls():
    urls = []

    for codename in get_codenames():
        for url in get_urls_from_codename(codename):
            urls.append(url)

    return urls


def scrape_cpu(url, conn, cur):
    print("scraping cpu...")

    DOMAIN = "https://www.techpowerup.com/"

    r = requests.get(DOMAIN + url)
    time.sleep(WAIT)
    if not r.ok:
        raise Exception("Something went wrong")

    soup = BeautifulSoup(r.text, "html.parser")

    tables = soup.find_all("section", class_="details")

    name = soup.find("h1", class_="cpuname").text
    keys = "('Name', "
    values = f"('{name}', "

    for table in tables[:-1]:
        for key, value in zip(table.find_all("th"), table.find_all("td")):
            key = re.sub(r'\s+', ' ', key.text).strip().replace(":", "")
            value = re.sub(r'\s+', ' ', value.text).strip()

            cur.execute(f'''SELECT 1 FROM PRAGMA_TABLE_INFO('cpus') WHERE name='{key}';''')
            if cur.fetchone() is None:
                cur.execute(f"ALTER TABLE cpus ADD COLUMN '{key}' TEXT;")

            conn.commit()

            keys += f"'{key}', "
            values += f"'{value}', "

    cur.execute(f'''SELECT 1 FROM cpus WHERE name='{name}';''')
    if cur.fetchone() is None:
        query = '''
        insert or ignore into cpus{} values {}; 
        '''.format(keys[:-2] + ")", values[:-2] + ")")

        cur.execute(query)

        print("cpu scraped!")
    else:
        print("cpu already exists!")

    conn.commit()


class Database:
    def __init__(self):
        self.conn = sqlite3.connect("cpus.db")
        self.cur = self.conn.cursor()

        self.cur.execute('''
        create table if not exists cpus (
            Name text primary key
        );
        ''')

        self.conn.commit()

    def __enter__(self):
        return self.conn, self.cur

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cur.close()
        self.conn.close()


with Database() as db:
    with open("missed.txt", "w") as file:
        for cpu in get_all_cpu_urls():
            retries = 2
            while retries > 0:
                try:
                    scrape_cpu(cpu, *db)
                except Exception as e:
                    print(f"ERROR: ({4 - retries}) {cpu} - {e}")
                    retries -= 1
                    if retries == 0:
                        file.write(f"{cpu} {e}\n")
                else:
                    break
