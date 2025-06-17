class RealEstateListing:
    def __init__(self, title, price, location, url, rooms):
        self.title = title
        self.price = price
        self.location = location
        self.url = url
        self.rooms = rooms

    def to_dict(self):
        return {
            "title": self.title,
            "price": self.price,
            "location": self.location,
            "url": self.url,
            "rooms": self.rooms
        }

    def __repr__(self):
        parts = [f"🏠 {self.title}"]

        if self.rooms:
            parts.append(f"{self.rooms} Zi")
        if self.price:
            parts.append(self.price)
        if self.location:
            parts.append(self.location)

        main_line = " | ".join(parts)
        return f"{main_line}\n🔗 {self.url}"

