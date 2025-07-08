from bs4 import BeautifulSoup
import requests
import sqlite3
import time
import re

WAIT = 6


def get_generations():
    print("getting generations...")

    HOME_PAGE = "https://www.techpowerup.com/gpu-specs"
    generations = []

    r = requests.get(HOME_PAGE)
    time.sleep(WAIT)
    if r.ok:
        soup = BeautifulSoup(r.text, "html.parser")

        dropdown = soup.find("select", id="generation")
        for gpu in dropdown.find_all("option")[1:]:
            generations.append(gpu.attrs["value"])

    print(f"found {len(generations)} generations")

    return generations


def get_urls_from_generation(codename):
    print("getting gpu urls...")

    CODENAME_QUERY = "https://www.techpowerup.com/gpu-specs/?generation="
    urls = []

    r = requests.get(CODENAME_QUERY + codename)
    time.sleep(WAIT)
    if r.ok:
        soup = BeautifulSoup(r.text, "html.parser")

        urls = []

        items = soup.find_all("td", class_="vendor-ATI")
        for item in items:
            urls.append(item.find("a").attrs["href"])

    print(f"found {len(urls)} urls")

    return urls


def get_all_gpu_urls():
    urls = []

    for generation in get_generations():
        for url in get_urls_from_generation(generation):
            urls.append(url)
        return urls
    return urls


def scrape_gpu(url, conn, cur):
    print("scraping gpu...")

    DOMAIN = "https://www.techpowerup.com/"

    r = requests.get(DOMAIN + url)
    time.sleep(WAIT)
    if not r.ok:
        raise Exception("Something went wrong")

    soup = BeautifulSoup(r.text, "html.parser")

    tables = soup.find_all("section", class_="details")

    name = soup.find("h1", class_="gpudb-name").text
    keys = "('Name', "
    values = f"('{name}', "

    for table in tables[:-1]:
        for key, value in zip(table.find_all("dt"), table.find_all("dd")):
            key = re.sub(r'\s+', ' ', key.text).strip()
            value = re.sub(r'\s+', ' ', value.text).strip()

            cur.execute(f'''SELECT 1 FROM PRAGMA_TABLE_INFO('gpus') WHERE name='{key}';''')
            if cur.fetchone() is None:
                cur.execute(f"ALTER TABLE gpus ADD COLUMN '{key}' TEXT;")

            conn.commit()

            keys += f"'{key}', "
            values += f"'{value}', "

    cur.execute(f'''SELECT 1 FROM gpus WHERE name='{name}';''')
    if cur.fetchone() is None:
        query = '''
        insert or ignore into gpus{} values {}; 
        '''.format(keys[:-2] + ")", values[:-2] + ")")

        cur.execute(query)

        print("gpu scraped!")
    else:
        print("gpu already exists!")

    conn.commit()


class Database:
    def __init__(self):
        self.conn = sqlite3.connect("gpus.db")
        self.cur = self.conn.cursor()

        self.cur.execute('''
        create table if not exists gpus (
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
    with open("missed_gpus.txt", "w") as file:
        for gpu in get_all_gpu_urls():
            retries = 2
            while retries > 0:
                try:
                    scrape_gpu(gpu, *db)
                except Exception as e:
                    print(f"ERROR: ({4 - retries}) {gpu} - {e}")
                    retries -= 1
                    if retries == 0:
                        file.write(f"{gpu} {e}\n")
                else:
                    break
