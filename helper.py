import requests

def clean_string(s):
    return s.replace('-', ' ').capitalize()

def parse_activity(data):
    user = data["data"]["discord_user"]
    spotify = data["data"].get("spotify", {})
    activities = data["data"].get("activities", [])

    result = {
        "username": user.get("username"),
        "user_id": user.get("id"),
        "status": data["data"].get("discord_status"),
        "listening_to_spotify": data["data"].get("listening_to_spotify", False),
        "spotify": None,
        "custom_status": None,
        "clan": {},
        "primary_guild": {},
    }

    if result["listening_to_spotify"] and spotify:
        result["spotify"] = {
            "song": spotify.get("song"),
            "artist": spotify.get("artist"),
            "album": spotify.get("album"),
            "album_art": spotify.get("album_art_url"),
            "start_timestamp": spotify.get("timestamps", {}).get("start"),
            "end_timestamp": spotify.get("timestamps", {}).get("end"),
            "track_id": spotify.get("track_id"),
        }

    custom_status = next((a for a in activities if a.get("name") == "Custom Status"), None)
    if custom_status:
        emoji = custom_status.get("emoji") or {}
        result["custom_status"] = {
            "state": custom_status.get("state"),
            "emoji_id": emoji.get("id"),
            "emoji_name": emoji.get("name"),
            "emoji_animated": emoji.get("animated", False),
            "end_timestamp": custom_status.get("timestamps", {}).get("end"),
        }

    clan = user.get("clan", {})
    primary_guild = user.get("primary_guild", {})

    result["clan"] = {
        "tag": clan.get("tag"),
        "guild_id": clan.get("identity_guild_id"),
        "badge": clan.get("badge"),
        "identity_enabled": clan.get("identity_enabled"),
    }

    result["primary_guild"] = {
        "tag": primary_guild.get("tag"),
        "guild_id": primary_guild.get("identity_guild_id"),
        "badge": primary_guild.get("badge"),
        "identity_enabled": primary_guild.get("identity_enabled"),
    }

    return result

def get_discord_activity(user_id):
    try:
        response = requests.get(f'https://lanyard.rest/v1/users/{user_id}')
        if response.status_code == 200:
            return parse_activity(response.json())
        print(f"Lanyard API error: {response.status_code}, {response.text}")
    except Exception as e:
        print(f"Error fetching Discord activity: {e}")
    return None
