"""
Centralized business data constants for Owl Internet.
Single source of truth for all business information.
"""

# Company Information
COMPANY_INFO = {
    "name": "Owl Internet",
    "founded": "2018",
    "service_areas": "Nationwide fiber and cable internet",
    "phone": "1-800-OWL-HELP",
    "email": "help@owlinternet.com",
    "website": "owlinternet.com",
    "hours": "24/7 customer support",
}

# Internet Plans
INTERNET_PLANS = {
    "100": {
        "name": "Basic",
        "speed": "one hundred megabits per second",
        "price": "thirty-nine dollars and ninety-nine cents per month",
        "description": "Perfect for browsing and streaming",
    },
    "300": {
        "name": "Standard",
        "speed": "three hundred megabits per second",
        "price": "fifty-nine dollars and ninety-nine cents per month",
        "description": "Great for families and remote work",
    },
    "500": {
        "name": "Advanced",
        "speed": "five hundred megabits per second",
        "price": "seventy-four dollars and ninety-nine cents per month",
        "description": "High-speed for power users",
    },
    "1000": {
        "name": "Premium",
        "speed": "one thousand megabits per second",
        "price": "eighty-nine dollars and ninety-nine cents per month",
        "description": "Ultra-fast for heavy usage and gaming",
    },
    "1gig": {
        "name": "Premium",
        "speed": "one thousand megabits per second",
        "price": "eighty-nine dollars and ninety-nine cents per month",
        "description": "Ultra-fast for heavy usage and gaming",
    },
    "gigabit": {
        "name": "Premium",
        "speed": "one thousand megabits per second",
        "price": "eighty-nine dollars and ninety-nine cents per month",
        "description": "Ultra-fast for heavy usage and gaming",
    },
}

# Router Information
ROUTER_MODELS = {
    "OWL-R2021": {
        "max_speed": "three hundred megabits per second",
        "wifi_standard": "WiFi 5",
        "upgrade_needed": "For speeds above three hundred megabits per second, upgrade to X5 router recommended",
        "upgrade_cost": "one hundred dollars (or twenty-five dollars for loyal customers)",
    },
    "OWL-R2019": {
        "max_speed": "one hundred fifty megabits per second",
        "wifi_standard": "WiFi 5",
        "upgrade_needed": "Router is limiting your plan speeds. X5 upgrade strongly recommended",
        "upgrade_cost": "one hundred dollars (or twenty-five dollars for loyal customers)",
    },
    "OWL-X5": {
        "max_speed": "one thousand plus megabits per second",
        "wifi_standard": "WiFi 6",
        "upgrade_needed": "Latest model - no upgrade needed",
        "upgrade_cost": "Not applicable",
    },
}

# Loyalty Tiers
LOYALTY_TIERS = {"new": "0-1 years", "loyal": "2-4 years", "premium": "5+ years"}
