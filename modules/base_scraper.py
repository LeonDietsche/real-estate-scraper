class BaseScraper:
    def __init__(self, config):
        self.config = config

    def get_name(self):
        return self.config.get("name", "unnamed")

    def scrape(self):
        raise NotImplementedError("Each scraper must implement scrape()")