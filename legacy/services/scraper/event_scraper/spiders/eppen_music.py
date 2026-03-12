import scrapy
from pathlib import Path
from datetime import datetime
import json
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from parser.parser import DatabaseParser


class EppenMusicSpider(scrapy.Spider):
    name = "eppen_music"
    BASE_URL = "https://www.ecodibergamo.it"

    def __init__(self):
        self.event_data = []

    custom_settings = {
        "LOG_LEVEL": "DEBUG",
    }

    def start_requests(self):

        urls = [
            "https://www.ecodibergamo.it/eventi/eppen/ricerca/?q=&page=1&start_date=&end_date=&category=musica&city=",
            "https://www.ecodibergamo.it/eventi/eppen/ricerca/?q=&page=2&start_date=&end_date=&category=musica&city=",
            "https://www.ecodibergamo.it/eventi/eppen/ricerca/?q=&page=3&start_date=&end_date=&category=musica&city=",
            "https://www.ecodibergamo.it/eventi/eppen/ricerca/?q=&page=4&start_date=&end_date=&category=musica&city=",
            "https://www.ecodibergamo.it/eventi/eppen/ricerca/?q=&page=5&start_date=&end_date=&category=musica&city=",
        ]

        for page_num, url in enumerate(urls, 1):
            yield scrapy.Request(
                url=url, callback=self.parse, meta={"page_num": page_num}
            )

    def parse(self, response):
        """Parameters to parse the main pages of the site and save the HTML content to file."""
        # name and save the file
        page_num = response.meta["page_num"]
        domain = response.url.split("/")[2].replace(".", "_")
        page = f"{domain}_page{page_num}"
        date_str = datetime.now().strftime("%Y%m%d")
        filename = f"eppenEvents-{page}-{date_str}.html"
        out_dir = Path(self.settings.get("OUTPUT_DIR", "out"))
        out_file = out_dir / filename
        out_file.write_bytes(response.body)
        self.log(f"Saved file {out_file}")
        url = "https://www.ecodibergamo.it"

        event_links = response.css("h5.card-title a::attr(href)").getall()

        for link in event_links[:5]:
            if link.startswith("http"):
                absolute_url = link
            else:
                absolute_url = self.BASE_URL + link

            yield scrapy.Request(
                url=absolute_url,
                callback=self.parse_event_details,
            )

    def parse_event_details(self, response):
        """function to parse each event details
        return a json file
        """
        # Extract JSON-LD data
        json_ld = response.xpath('//script[@type="application/ld+json"]/text()').get()
        event_json = None

        if json_ld:
            try:
                event_json = json.loads(json_ld)
            except json.JSONDecodeError:
                pass

        event_data = {
            # CORE EVENT FIELDS (raw data only)
            "name": (response.css(".col-12.col-lg-10 h1::text").get() or "").strip(),
            "description": None,
            "genre": (
                response.css(".col-12.col-lg-10 .article-section-category::text")
                .getall()[-1]
                .strip()
                .split("/")[-1]
                .strip()
                if response.css(
                    ".col-12.col-lg-10 .article-section-category::text"
                ).getall()
                else None
            ),
            "tags": None,
            "image": None,
            "link": response.url,
            # EVENT TIMING
            "start_date": (
                event_json.get("startDate")[:10]
                if event_json and event_json.get("startDate")
                else None
            ),
            "start_time": (
                event_json.get("startDate")[11:16]
                if event_json and event_json.get("startDate")
                else None
            ),
            "end_date": (
                event_json.get("endDate")[:10]
                if event_json and event_json.get("endDate")
                else None
            ),
            "end_time": (
                event_json.get("endDate")[11:16]
                if event_json and event_json.get("endDate")
                else None
            ),
            # EVENT DETAILS
            "language": None,
            "age_restriction": None,
            "age_recommended": None,
            "organizer": None,
            "promoter": None,
            # CONTACT INFO
            "contact_name": None,
            "contact_email": None,
            "contact_phone": None,
            # TICKET INFO
            "ticket_link": response.css(".mb-3 a::attr(href)").get(),
            # PRICING
            "price_regular": None,
            "price_discounted": None,
            "price_comments": None,
            # EXTRACTED TEXT
            "extracted_text": response.css(".col-12.col-lg-10 h2::text").get(),
            # VENUE DATA (raw venue info)
            "venue_name": None,
            "venue_description": None,
            "venue_address": None,
            "venue_city": None,
            "venue_country": None,
            "venue_capacity": None,
            "venue_latitude": None,
            "venue_longitude": None,
            "venue_link": None,
            "venue_image": None,
            "venue_contact_name": None,
            "venue_contact_email": None,
            "venue_contact_phone": None,
            "venue_founded_year": None,
            # ARTIST DATA (raw artist info)
            "artist1_name": None,
            "artist1_description": None,
            "artist1_summary": None,
            "artist1_components": None,
            "artist1_country": None,
            "artist1_city": None,
            "artist1_genres": None,
            "artist1_link": None,
            "artist1_image": None,
            "artist1_contact_name": None,
            "artist1_contact_email": None,
            "artist1_contact_phone": None,
            "artist1_founded_year": None,
            # ARTIST2 DATA
            "artist2_name": None,
            "artist2_description": None,
            "artist2_summary": None,
            "artist2_components": None,
            "artist2_country": None,
            "artist2_city": None,
            "artist2_genres": None,
            "artist2_link": None,
            "artist2_image": None,
            "artist2_contact_name": None,
            "artist2_contact_email": None,
            "artist2_contact_phone": None,
            "artist2_founded_year": None,
            # ARTIST3 DATA
            "artist3_name": None,
            "artist3_description": None,
            "artist3_summary": None,
            "artist3_components": None,
            "artist3_country": None,
            "artist3_city": None,
            "artist3_genres": None,
            "artist3_link": None,
            "artist3_image": None,
            "artist3_contact_name": None,
            "artist3_contact_email": None,
            "artist3_contact_phone": None,
            "artist3_founded_year": None,
        }

        self.event_data.append(event_data)
        yield event_data

    def closed(self, reason):
        """Scrapy method called when spider finishes - save all collected data"""
        output_data = {
            "title": "Events Scraped from Eco di Bergamo",
            "scraped_date": datetime.now().strftime("%Y-%m-%d"),
            "website": self.BASE_URL,
            "total_events": len(self.event_data),
            "events": self.event_data,
        }

        filename = f"events_{datetime.now().strftime('%Y%m%d')}.json"
        out_dir = Path("out")
        out_dir.mkdir(exist_ok=True)

        with open(out_dir / filename, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        self.logger.info(f"Saved {len(self.event_data)} events to {out_dir / filename}")

        # Send data to database
        self.parse_to_db()

    def parse_to_db(self):
        """Parse event data and send to database"""
        if not self.event_data:
            self.logger.warning("No event data to parse")
            return

        from parser.config import settings

        db_parser = DatabaseParser(settings.POSTGRES_URL)

        try:
            inserted_count = db_parser.insert_events(
                events_data=self.event_data,
                source_website=self.BASE_URL,
            )

            self.logger.info(
                f"Successfully inserted {inserted_count} events into database"
            )

            total_events = db_parser.get_events_count()
            self.logger.info(f"Total events in database: {total_events}")

        except Exception as e:
            self.logger.error(f"Error inserting events into database: {e}")
