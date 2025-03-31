from sqlalchemy import Column, Integer, String, Text, ForeignKey, Float, DateTime, BigInteger, Table
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import relationship

# Define SQLAlchemy Base
Base = declarative_base()

# Define association table for movie-genre relationship
movie_genres = Table(
    'movie_genres',
    Base.metadata,
    Column('movie_id', Integer, ForeignKey('movies.id'), primary_key=True),
    Column('genre_id', Integer, ForeignKey('genres.id'), primary_key=True)
)

# Define SQLAlchemy models
class Movie(Base):
    __tablename__ = 'movies'
    
    id = Column(Integer, primary_key=True)
    plex_key = Column(String(50), unique=True)
    title = Column(String(255), nullable=False)
    year = Column(Integer)
    date_added = Column(DateTime)
    duration = Column(Integer)
    summary = Column(Text)
    content_rating = Column(String(20))
    studio = Column(String(255))
    file_path = Column(String(512))
    file_size = Column(BigInteger)
    last_updated = Column(DateTime)
    
    genres = relationship("Genre", secondary=movie_genres, back_populates="movies")
    ratings = relationship("Rating", back_populates="movie", cascade="all, delete-orphan")
    play_history = relationship("PlayHistory", back_populates="movie", cascade="all, delete-orphan")

class Genre(Base):
    __tablename__ = 'genres'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True)
    
    movies = relationship("Movie", secondary=movie_genres, back_populates="genres")

class Rating(Base):
    __tablename__ = 'ratings'
    
    id = Column(Integer, primary_key=True)
    movie_id = Column(Integer, ForeignKey('movies.id'))
    source = Column(String(50))
    rating = Column(Float(precision=2))
    votes = Column(Integer)
    
    movie = relationship("Movie", back_populates="ratings")

class PlayHistory(Base):
    __tablename__ = 'play_history'
    
    id = Column(Integer, primary_key=True)
    movie_id = Column(Integer, ForeignKey('movies.id'))
    account_id = Column(Integer)
    account_name = Column(String(100))
    device_name = Column(String(100))
    played_at = Column(DateTime)
    percent_complete = Column(Float(precision=2))
    
    movie = relationship("Movie", back_populates="play_history")