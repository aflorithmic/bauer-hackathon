import os
from time import sleep
from datetime import datetime
from zoneinfo import ZoneInfo
from abc import ABC, abstractmethod

import num2words
import requests


class AudioformAdBuilder(ABC):
    def __init__(self, audiostack_api_key: str):
        self.audiostack_api_key = audiostack_api_key

    @abstractmethod
    def build_audioform(self, *args, **kwargs) -> dict:
        """
        Abstract method to build the audioform.
        Should be implemented in subclasses.
        """
        raise NotImplementedError("Subclasses must implement this method")

    def generate_ad(self, audioform: dict) -> str:
        """
        Generates an ad from an audioform and returns the audio URL
        """
        response = requests.post(
            "https://v2.api.audio/audioforms",
            json=audioform,
            headers={"x-api-key": self.audiostack_api_key},
        )
        if response.status_code >= 400:
            print("Error:", response.status_code, response.text)
            raise Exception("Failed to create audioform")

        d = response.json()
        response = requests.get(
            f"https://v2.api.audio/audioforms/{d['data']['audioformId']}",
            headers={"x-api-key": self.audiostack_api_key, "version": "4"},
        )
        while response.status_code == 202:
            print("Waiting for audioform to be ready...")
            sleep(5)
            response = requests.get(
                f"https://v2.api.audio/audioforms/{d['data']['audioformId']}",
                headers={"x-api-key": self.audiostack_api_key, "version": "4"},
            )
        print(response.text)
        return response.json()["data"]["result"]["delivery"]["uri"]


class Coinspot(AudioformAdBuilder):
    voice = "nathaniel"  # README: Query the Voice Library (POST /assets/voices/query)
    soundbed = "bounce_along"  # README: Query the Sound Template Library (POST /assets/sound-templates/query)
    total_length = 30

    def get_time_of_day(self, timezone):
        dt = datetime.now(ZoneInfo(timezone))
        current_hour = dt.hour
        if 4 <= current_hour < 12:
            return "morning"
        elif 11 <= current_hour < 18:
            return "afternoon"
        elif 17 <= current_hour < 22:
            return "evening"
        else:
            return "night"

    def get_value_change(self, percentage: float) -> str:
        digit_map = {
            "0": "zero",
            "1": "one",
            "2": "two",
            "3": "three",
            "4": "four",
            "5": "five",
            "6": "six",
            "7": "seven",
            "8": "eight",
            "9": "nine",
            ".": " point ",
            ",": " point ",
            "%": " percent",
        }

        # Round the percentage value to 1 decimal place
        rounded_percentage = round(abs(percentage), 1)

        # Convert to string and handle "x.0" case to remove decimal part
        percentage_str = str(rounded_percentage)
        if percentage_str.endswith(".0"):
            percentage_str = percentage_str[:-2]  # Remove the ".0" part

        # Convert to words for numbers less than 10
        formatted_percentage = ""
        if float(percentage_str) < 10:
            # Convert each character to its word representation
            for char in percentage_str:
                if char in digit_map:
                    formatted_percentage += digit_map[char]
                else:
                    formatted_percentage += char
        else:
            decimal_split = percentage_str.split(".")
            if len(decimal_split) == 2:
                formatted_percentage = f"{decimal_split[0]} point {decimal_split[1]}"
            else:
                formatted_percentage = percentage_str

        if percentage > 0:
            value_change = f"{formatted_percentage} percent increase"
        elif percentage < 0:
            value_change = f"{formatted_percentage} percent decrease"
        else:
            raise ValueError("Percentage cannot be zero for value change.")

        return value_change

    def get_btc_price(self):
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": "bitcoin",
            "vs_currencies": "aud",
            "include_24hr_change": "true",
        }

        response = requests.get(url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()["bitcoin"]

        return {
            "price": int(data["aud"]),
            "percentage": round(float(data["aud_24h_change"]), 1),
        }

    def build_audioform(
        self, location: str, time_of_day: str, btc_price, btc_percentage_change
    ):
        """
        Builds an Audioform for Coinspot ad.
        More about Audioforms: https://docs.audiostack.ai/
        """
        value_change = self.get_value_change(btc_percentage_change)

        return {
            "audioform": {
                "header": {"version": "4"},
                "assets": {
                    "greeting": {
                        "type": "tts",
                        "text": f"Good {time_of_day}, {location}! Here's your Live Crypto Currency update, thanks to CoinSpot!",
                        "anchor": f"{time_of_day}-{location}-0",
                        "voiceRef": "main voice",
                    },
                    "dynamic": {
                        "type": "tts",
                        "text": f"""While you've been listening to your favourite podcast, Bitcoin is making moves and it's now trading at {num2words.num2words(int(btc_price))} dollars - that's a {value_change} within the last twenty four hours!""",
                        "voiceRef": "main voice",
                    },
                    "fill": {
                        "type": "tts",
                        "text": "CoinSpot! Australia's home base for Crypto. Get started buying Bitcoin, Ethereum, and a world of other cryptocurrencies in just minutes! So if you're ready to dive into crypto in a safe and easy way, sign up now at coinspot.com.au",
                        # anchor is a cache seed - it's desirable that non-dynamic parts of the ad always sound the same
                        # change the anchor to get a different result for the same input
                        "anchor": "fill-0",
                        "voiceRef": "main voice",
                    },
                    "main voice": {"type": "voice", "voiceAlias": self.voice},
                    "sound template 0": {
                        "type": "soundTemplate",
                        "soundTemplateAlias": self.soundbed,
                        "segment": "main",
                    },
                },
                "production": {
                    "constraints": [
                        {
                            "type": "timeConstraint",
                            # the sum of these assets must fit in groupTargetDuration
                            "assets": ["greeting", "dynamic", "fill"],
                            "groupTargetDuration": self.total_length
                            - 2,  # 1s for margins, 1s for fade out
                            "targetDurationSpeedUpLimit": 2,
                            "targetDurationSlowDownLimit": 1,  # never slow down assets
                        }
                    ],
                    "arrangement": {
                        "forcedDuration": self.total_length,
                        "fadeOut": 1.0,
                        "sections": [
                            {
                                "layers": [
                                    {
                                        "clips": [
                                            {
                                                "assetRef": "greeting",
                                                "marginStart": 0,
                                                "marginEnd": 0.5,  # 0.5s of silence at the end of the asset
                                            },
                                            {
                                                "assetRef": "dynamic",
                                                "marginEnd": 0.3,
                                            },
                                            {
                                                "assetRef": "fill",
                                                "marginEnd": 0.3,
                                            },
                                        ]
                                    },
                                ],
                                "soundTemplateRef": "sound template 0",
                                "forcedDuration": self.total_length,
                            },
                        ],
                    },
                    "mixingPreset": "musicenhanced",
                },
                "delivery": {
                    "loudnessPreset": "spotify",
                    "encoderPreset": "mp3",
                    "public": True,
                },
            },
        }


if __name__ == "__main__":
    builder = Coinspot(audiostack_api_key=os.getenv("AUDIOSTACK_API_KEY"))

    time_of_day = builder.get_time_of_day("Australia/Sydney")
    btc_price = builder.get_btc_price()

    audioform = builder.build_audioform(
        location="Sydney",
        time_of_day=time_of_day,
        btc_price=btc_price["price"],
        btc_percentage_change=btc_price["percentage"],
    )
    ad_url = builder.generate_ad(audioform)
    print("Generated ad URL:", ad_url)
