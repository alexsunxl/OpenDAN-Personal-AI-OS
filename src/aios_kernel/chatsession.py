
import sqlite3 # Because sqlite3 IO operation is small, so we can use sqlite3 directly.(so we don't need to use async sqlite3 now)
from sqlite3 import Error
import logging
import threading
import datetime
import uuid

from .agent_message import AgentMsg

class ChatSessionDB:
    def __init__(self, db_file):
        """ initialize db connection """
        self.local = threading.local()
        self.db_file = db_file
        self._get_conn()

    def _get_conn(self):
        """ get db connection """
        if not hasattr(self.local, 'conn'):
            self.local.conn = self._create_connection(self.db_file)
        return self.local.conn

    def _create_connection(self, db_file):
        """ create a database connection to a SQLite database """
        conn = None
        try:
            conn = sqlite3.connect(db_file)
        except Error as e:
            logging.error("Error occurred while connecting to database: %s", e)
            return None

        if conn:
            self._create_table(conn)

        return conn
    
    def close(self):
        if not hasattr(self.local, 'conn'):
            return 
        self.local.conn.close()

    def _create_table(self, conn):
        """ create table """
        try:
            # create sessions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ChatSessions (
                    SessionID TEXT PRIMARY KEY,
                    SessionOwner TEXT,
                    SessionTopic TEXT,
                    StartTime TEXT
                );
            """)

            # create messages table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS Messages (
                    MessageID TEXT PRIMARY KEY,
                    SessionID TEXT,
                    SenderID TEXT,
                    ReceiverID TEXT,
                    Timestamp TEXT,
                    Content TEXT,
                    Status INTEGER
                );
            """)
            conn.commit()
        except Error as e:
            logging.error("Error occurred while creating tables: %s", e)

    def insert_chatsession(self, session_id, session_owner,session_topic, start_time):
        """ insert a new session into the ChatSessions table """
        try:
            conn = self._get_conn()
            conn.execute("""
                INSERT INTO ChatSessions (SessionID, SessionOwner,SessionTopic, StartTime)
                VALUES (?,?, ?, ?)
            """, (session_id, session_owner,session_topic, start_time))
            conn.commit()
            return 0  # return 0 if successful
        except Error as e:
            logging.error("Error occurred while inserting session: %s", e)
            return -1  # return -1 if an error occurs

    def insert_message(self, message_id, session_id, sender_id, receiver_id, timestamp, content, status):
        """ insert a new message into the Messages table """
        try:
            conn = self._get_conn()
            conn.execute("""
                INSERT INTO Messages (MessageID, SessionID, SenderID, ReceiverID, Timestamp, Content, Status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (message_id, session_id, sender_id, receiver_id, timestamp, content, status))
            conn.commit()
            return 0  # return 0 if successful
        except Error as e:
            logging.error("Error occurred while inserting message: %s", e)
            return -1  # return -1 if an error occurs
    
    def get_chatsession_by_id(self, session_id):
        """Get a message by its ID"""
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("SELECT * FROM ChatSessions WHERE SessionID = ?", (session_id,))
        chatsession = c.fetchone()
        return chatsession
    
    def get_chatsession_by_owner_topic(self, owner_id, topic):
        """Get a chatsession by its owner and topic"""
        conn = self._get_conn()
        c = conn.cursor()
        c.execute("SELECT * FROM ChatSessions WHERE SessionOwner = ? AND SessionTopic = ?", (owner_id,topic))
        chatsession = c.fetchone()
        return chatsession

    def get_chatsessions(self, limit, offset):
        """ retrieve sessions with pagination """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM ChatSessions
                ORDER BY StartTime DESC
                LIMIT ? OFFSET ?
            """, (limit, offset))
            results = cursor.fetchall()
            #self.close()
            return results  # return 0 and the result if successful
        except Error as e:
            logging.error("Error occurred while getting sessions: %s", e)
            return -1, None  # return -1 and None if an error occurs
        
    def get_message_by_id(self, message_id):
        """Get a message by its ID"""
        conn =self._get_conn()
        c = conn.cursor()
        c.execute("SELECT MessageID,SessionID,SenderID,ReceiverID,Timestamp,Content,Status FROM Messages WHERE MessageID = ?", (message_id,))
        message = c.fetchone()
        return message

    def get_messages(self, session_id, limit, offset):
        """ retrieve messages of a session with pagination """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT MessageID,SessionID,SenderID,ReceiverID,Timestamp,Content,Status FROM Messages
                WHERE SessionID = ?
                ORDER BY Timestamp DESC
                LIMIT ? OFFSET ?
            """, (session_id, limit, offset))
            results = cursor.fetchall()
            #self.close()
            return results  # return 0 and the result if successful
        except Error as e:
            logging.error("Error occurred while getting messages: %s", e)
            return -1, None  # return -1 and None if an error occurs

    def update_message_status(self, message_id, status):
        """ update the status of a message """
        try:
            conn = self._get_conn()
            conn.execute("""
                UPDATE Messages
                SET Status = ?
                WHERE MessageID = ?
            """, (status, message_id))
            conn.commit()
            return 0  # return 0 if successful
        except Error as e:
            logging.error("Error occurred while updating message status: %s", e)
            return -1  # return -1 if an error occurs
        

# chat session store the chat history between owner and agent
# chat session might be large, so can read / write at stream mode.
class AIChatSession:
    _dbs = {}
    #@classmethod
    #async def get_session_by_id(cls,session_id:str,db_path:str):
    #    db = cls._dbs.get(db_path)
    #    if db is None:
    #        db = ChatSessionDB(db_path)
    #        cls._dbs[db_path] = db
    #    db.get_chatsession_by_id(session_id)
    #    #result = AIChatSession()
    
    @classmethod
    def get_session(cls,owner_id:str,session_topic:str,db_path:str,auto_create = True) -> str:
        db = cls._dbs.get(db_path)
        if db is None:
            db = ChatSessionDB(db_path)
            cls._dbs[db_path] = db

        result = None
        session = db.get_chatsession_by_owner_topic(owner_id,session_topic)
        if session is None:
            if auto_create:
                session_id = "CS#" + uuid.uuid4().hex
                db.insert_chatsession(session_id,owner_id,session_topic,datetime.datetime.now())
                result = AIChatSession(owner_id,session_id,db)
        else:
            result = AIChatSession(owner_id,session[0],db)
            result.topic = session_topic

        return result          
    

    def __init__(self,owner_id:str, session_id:str, db:ChatSessionDB) -> None:
        self.owner_id :str = owner_id
        self.session_id : str = session_id
        self.db : ChatSessionDB = db
        
        self.topic : str = None
        self.start_time : str = None

    def get_owner_id(self) -> str:
        return self.owner_id
    
    def read_history(self, number:int=10,offset=0) -> [AgentMsg]:
        msgs = self.db.get_messages(self.session_id, number, offset)
        result = []
        for msg in msgs:
            agent_msg = AgentMsg()
            agent_msg.id = msg[0]
            agent_msg.sender = msg[2]
            agent_msg.target = msg[3]
            agent_msg.create_time = msg[4]
            agent_msg.body = msg[5]
            # agent_msg.state = msg[6]

            result.append(agent_msg)
        return result

    def append(self,msg:AgentMsg) -> None:
        self.db.insert_message(msg.id,self.session_id,msg.sender,msg.target,msg.create_time,msg.body,0)

    def append_post(self,msg:AgentMsg) -> None:
        """append msg to session, msg is post from session (owner => msg.target)"""
        #assert msg.sender == self.owner_id,"post message means msg.sender == self.owner_id"
        self.append(msg)
        

    def append_recv(self,msg:AgentMsg) -> None:
        """append msg to session, msg is recv from msg'sender (msg.sender => owner)"""
        #assert msg.target == self.owner_id,"recv message means msg.target == self.owner_id"
        self.append(msg)        

    #def attach_event_handler(self,handler) -> None:
    #    """chat session changed event handler"""
    #    pass

    #TODO : add iterator interface for read chat history 