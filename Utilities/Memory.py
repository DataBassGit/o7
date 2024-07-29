from agentforge.utils.chroma_utils import ChromaUtils
from agentforge.utils.functions.Logger import Logger
from Utilities.Parsers import MessageParser


class Memory:

    def __init__(self, persona_file, persona_name):
        self.logger = Logger('Memory')
        self.memory = ChromaUtils()
        self.parser = MessageParser
        self.persona_file = persona_file
        self.persona = persona_name
        self.message_batch = None
        self.user_message = None
        self.cognition = None
        self.response = None
        self.current_memories = []
        self.current_journals = []

    def save_channel_simple(self, message):
        channel = message.get('channel')
        message_text = message.get('message')
        author = message.get('author')
        time = message.get('timestamp')
        collection_name = f"a{channel}_chat_history"
        collection_name = self.parser.format_string(collection_name)

        collection_size = self.memory.search_metadata_min_max(collection_name, 'id', 'max')
        if collection_size is None or "target" not in collection_size:
            memory_id = ["1"]
            collection_int = 1
        else:
            memory_id = [str(collection_size["target"] + 1 if collection_size["target"] is not None else 1)]
            collection_int = collection_size["target"] + 1

        metadata = {
            "id": collection_int,
            "User": author,
            "Channel": channel,
            "Timestamp": time
        }

        self.memory.save_memory(collection_name=collection_name,
                                data=message_text,
                                ids=memory_id,
                                metadata=[metadata])
        pass

    def save_dm_simple(self, message):
        channel = message.get('channel')
        message_text = message.get('message')
        author = message.get('author')
        time = message.get('timestamp')
        collection_name = f"dm{author}_chat_history"
        collection_name = self.parser.format_string(collection_name)

        collection_size = self.memory.search_metadata_min_max(collection_name, 'id', 'max')
        if collection_size is None or "target" not in collection_size:
            memory_id = ["1"]
            collection_int = 1
        else:
            memory_id = [str(collection_size["target"] + 1 if collection_size["target"] is not None else 1)]
            collection_int = collection_size["target"] + 1

        metadata = {
            "id": collection_int,
            "User": author,
            "Channel": channel,
            "Timestamp": time
        }

        self.memory.save_memory(collection_name=collection_name,
                                data=message_text,
                                ids=memory_id,
                                metadata=[metadata])
        pass

    def fetch_history(self, collection_name, prefix="a", query=None, is_user_specific=False, query_size: int = 20):
        """
        Fetch and parse history for users and channels
        :param collection_name: Channel name or username
        :param prefix: Prefix for direct messages ('dm') or standard ('a'). Defaults to 'a'.
        :param query: Search the history. Defaults to None for most recent.
        :param is_user_specific: Chooses parser. True for user history, False for channel history
        :param query_size: Number of results. Defaults to 20.
        :return: Returns formatted history.
        """
        collection_name = f"{prefix}{collection_name}_chat_history"
        collection_name = self.parser.format_string(collection_name)
        self.logger.log(f"Fetch History from: {collection_name}\n", 'debug', 'Memory')

        collection_size = self.memory.count_collection(collection_name)

        if collection_size == 0:
            return "No Results!"

        qsize = max(collection_size - query_size, 0)

        # Adjust the method of fetching history based on whether it's user-specific
        if is_user_specific and query:
            if qsize == 0:
                qsize = 1
            history = self.memory.query_memory(collection_name=collection_name, query=query, num_results=qsize)
            formatted_history = self.parser.format_user_specific_history_entries(history)
        else:
            filters = {"id": {"$gte": qsize}}
            history = self.memory.load_collection(collection_name=collection_name, where=filters)
            formatted_history = self.parser.format_general_history_entries(history)

        self.logger.log(f"Fetched History:\n{history}\n", 'debug', 'Memory')
        return formatted_history

    def get_persona(self):
        return self.persona_file

    def save_all_memory(self):
        self.save_category_memory()
        self.save_channel_memory()
        self.save_bot_response()
        self.save_user_history()
        self.logger.log(f"Saved all memories.", 'debug', 'Trinity')

        # Save Journal would go here, if I had it! - This was implemented in save_channel_memory()

    def set_memory_info(self,   message_batch: dict, cognition: dict, response: str):
        self.message_batch = message_batch
        self.user_message = message_batch
        self.cognition = cognition
        self.response = response

    def save_to_collection(self, collection_name: str, chat_message: dict, response_message: str,
                                 metadata_extra=None):
        collection_size = self.memory.search_metadata_min_max(collection_name, 'id', 'max')
        if collection_size is None or "target" not in collection_size:
            memory_id = ["1"]
            collection_int = 1
        else:
            memory_id = [str(collection_size["target"] + 1 if collection_size["target"] is not None else 1)]
            collection_int = collection_size["target"] + 1

        metadata = {
            "id": collection_int,
            "Response": response_message,
            "Emotion": self.cognition["thought"].get("Emotion"),
            "InnerThought": self.cognition["thought"].get("Inner Thought"),
            "Reason": self.cognition["reflect"].get("Reason"),
            "User": chat_message["author"],
            # "Mentions": chat_message["mentions"],
            "Channel": str(chat_message["channel"]),
            "Categories": str(self.cognition["thought"]["Categories"])
        }
        # Need to implement a last accessed metadata

        if metadata_extra:
            metadata.update(metadata_extra)

        message = [chat_message["message"]]
        self.memory.save_memory(collection_name=collection_name, data=message, ids=memory_id, metadata=[metadata])
        self.logger.log(f"\nSaved to {collection_name}\n"
                        f"Data (Message)={message}\n"
                        f"ID={memory_id}\n"
                        f"Metadata={metadata}",
                        'debug', 'Trinity')

    def save_category_memory(self):
        categories = self.cognition["thought"]["Categories"].split(",")
        for category in categories:
            collection_name = f"{category.strip()}"
            category_collection = self.parser.format_string(collection_name)
            self.logger.log(f"Saving Category to: {category_collection}\nMessage:\n{self.user_message}",
                            'debug', 'Memory')
            self.save_to_collection(category_collection, self.user_message, self.response)

    def save_channel_memory(self):
        collection_name = f"a{self.user_message['channel']}_chat_history"
        collection_name = self.parser.format_string(collection_name)
        for index, message in enumerate(self.message_batch):
            metadata_extra = {}
            bot_response = self.response
            self.logger.log(f"Saving Channel to: {collection_name}\nMessage:\n{message}", 'debug', 'Memory')
            self.save_to_collection(collection_name, message, bot_response, metadata_extra)
            self.save_to_collection('journal_log_table', message, bot_response, metadata_extra)

    def save_bot_response(self):
        message = self.user_message.copy()
        message['message'] = self.response
        message['author'] = self.persona

        collection_name = f"a{message['channel']}_chat_history"
        collection_name = self.parser.format_string(collection_name)
        self.logger.log(f"Saving Bot Response to: {collection_name}\nMessage:\n{message}", 'debug', 'Memory')
        self.save_to_collection(collection_name, message, self.user_message['message'])
        self.save_to_collection('journal_log_table', message, self.user_message['message'])

    # this also needs to be reviewed
    def save_user_history(self):
        collection_name = f"a{self.user_message['author']}_chat_history"
        collection_name = self.parser.format_string(collection_name)
        self.logger.log(f"Saving User History to: {collection_name}\nMessage:\n{self.user_message}", 'debug', 'Memory')
        self.save_to_collection(collection_name, self.user_message, self.response)

    def get_current_memories(self):
        if self.current_memories:
            memories = str(self.current_memories[0])
            return memories

        return 'No Memories Found.'

    def get_current_journals(self):
        if self.current_journals:
            memories = str(self.current_journals[0])
            return memories

        return 'No Memories Found.'

    def recall_recent_memories(self):
        pass

    def recall_categories(self, message, categories, num_memories_per_category: int = 10):
        self.logger.log(f"Recalling {num_memories_per_category} Memories per Category", 'debug', 'Memory')
        categories = categories.split(",")
        for category in categories:
            collection_name = f"{category.strip()}"
            category_collection = self.parser.format_string(collection_name)
            self.logger.log(f"Fetching Category: {category_collection}", 'debug', 'Memory')
            recalled_memories = self.memory.query_memory(collection_name=category_collection,
                                                          query=message,
                                                          num_results=num_memories_per_category)
            if recalled_memories:
                self.logger.log(f"Recalled Memories:\n{recalled_memories}", 'debug', 'Memory')
                memories = self.parser.format_user_specific_history_entries(recalled_memories)
                # Add recalled memories to current memories
                self.current_memories.append(memories)
                return

            self.logger.log(f"No Memories Recalled For Category: {category}", 'debug', 'Memory')

    def save_journal_log(self):
        collection_name = 'journal_log_table'
        for index, message in enumerate(self.message_batch):
            metadata_extra = {}
            bot_response = self.response
            self.logger.log(f"Saving Channel to: {collection_name}\nMessage:\n{message}",
                            'debug', 'Memory')
            self.save_to_collection(collection_name, message, bot_response, metadata_extra)

    def recall_journal_entry(self, message, categories, num_entries: int = 2):
        self.logger.log(f"Recalling {num_entries} entries from the journal", 'debug', 'Memory')
        journal_query = f"{message}\n\n Related Categories: {categories}"
        collection_name = 'journal_chunks_table'
        journal_chunks = self.memory.query_memory(
            collection_name=collection_name,
            query=journal_query,
            num_results=num_entries
        )
        if journal_chunks:
            self.logger.log(f"Recalled Memories:\n{journal_chunks}", 'debug', 'Memory')

            # Set the relevance threshold
            relevance_threshold = 0.65  # Adjust this value as needed

            # Create a dictionary to store the recalled memories
            recalled_memories = {
                'ids': [],
                'embeddings': None,
                'metadatas': [],
                'documents': []
            }

            for i in range(len(journal_chunks['ids'])):
                distance = journal_chunks['distances'][i]
                if distance >= relevance_threshold:
                    source_id = journal_chunks['metadatas'][i]['Source_ID']

                    filter = {"id": {"$eq": source_id}}

                    # Retrieve the full journal entry based on the source_id
                    full_entry = self.memory.load_collection(
                        collection_name='whole_journal_entries',
                        where=filter
                    )

                    if full_entry:
                        print(f"Full Entry: {full_entry}")
                        # Add the relevant fields to the recalled_memories dictionary
                        recalled_memories['ids'].append(full_entry['ids'][0])
                        recalled_memories['metadatas'].append({key: value for key, value in full_entry['metadatas'][0].items() if key.lower() not in ['source', 'isotimestamp', 'unixtimestamp']})
                        recalled_memories['documents'].append(full_entry['documents'][0])

            print(f"Full Entries Appended: {recalled_memories}")
            memories = self.parser.format_user_specific_history_entries(recalled_memories)
            # Add recalled memories to current memories
            self.current_journals.append(memories)
            print(f"\n\nCurrent Memories:\n{self.current_memories}")
            return memories

    def wipe_current_memories(self):
        self.current_memories = []
        self.current_journals = []

    async def check_journal(self):
        count = self.memory.count_collection('journal_log_table')
        print(count)
        if count >= 100:
            from Utilities.Journal import Journal
            journal_function = Journal()
            journal_written = journal_function.do_journal()
            if journal_written:
                self.memory.delete_collection('journal_log_table')
            return journal_written
        else:
            return None

