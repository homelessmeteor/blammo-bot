"""
Mock twitchbot module for testing purposes
"""

class Message:
    """Mock Message class for testing"""
    def __init__(self, content="", author="testuser", channel_name="testchannel"):
        self.content = content
        self.author = author
        self.channel_name = channel_name
        self.channel = MockChannel(channel_name)
    
    async def reply(self, message, as_twitch_reply=False):
        """Mock reply method"""
        pass

class MockChannel:
    """Mock Channel class for testing"""
    def __init__(self, name):
        self.name = name