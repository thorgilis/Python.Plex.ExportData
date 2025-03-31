import os
import logging
from datetime import datetime
from plexapi.server import PlexServer
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import  sessionmaker
from sqlalchemy.dialects.postgresql import insert
from data.models import Base, Movie, Genre, Rating, PlayHistory

# Load environment variables from .env file
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('plex_pipeline')

# Plex configuration from environment variables
PLEX_BASE_URL = os.getenv('PLEX_BASE_URL', 'http://192.168.0.61:32400')
PLEX_TOKEN = os.getenv('PLEX_TOKEN')

# PostgreSQL configuration from environment variables
DB_HOST = os.getenv('DB_HOST', '192.168.0.63')
DB_NAME = os.getenv('DB_NAME', 'plex_stats')
DB_USER = os.getenv('DB_USER', 'myuser')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_PORT = os.getenv('DB_PORT', '5432')


def connect_to_plex():
    """Connect to the Plex server"""
    if not PLEX_TOKEN:
        logger.error("PLEX_TOKEN environment variable not set")
        raise ValueError("PLEX_TOKEN environment variable not set")
    
    try:
        plex = PlexServer(PLEX_BASE_URL, PLEX_TOKEN)
        logger.info(f"Connected to Plex server: {plex.friendlyName}")
        return plex
    except Exception as e:
        logger.error(f"Failed to connect to Plex server: {e}")
        raise

def create_db_engine():
    """Create SQLAlchemy engine for PostgreSQL"""
    if not DB_PASSWORD:
        logger.error("DB_PASSWORD environment variable not set")
        raise ValueError("DB_PASSWORD environment variable not set")
    
    connection_string = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_engine(connection_string)
    logger.info("Created SQLAlchemy engine for PostgreSQL database")
    return engine

def setup_database(engine):
    """Create necessary tables in the database"""
    Base.metadata.create_all(engine)
    logger.info("Database schema set up successfully")

def calculate_percent_complete(media_item, history_item):
    """Calculate the actual percentage complete for a viewing session"""
    try:
        # Try to use viewOffset if available
        if hasattr(history_item, 'viewOffset') and hasattr(media_item, 'duration'):
            if media_item.duration > 0:
                return min(100.0, (history_item.viewOffset / media_item.duration) * 100)
        
        # If marked as watched, assume 100%
        if hasattr(history_item, 'viewCount') and history_item.viewCount > 0:
            return 100.0
            
        # Default to 95% if we can't calculate
        return 95.0
    except:
        return 95.0

def fetch_and_store_movies(plex, session):
    """Fetch movies from Plex and store in PostgreSQL"""
    try:
        # Get all movie sections
        movie_sections = [section for section in plex.library.sections() if section.type == 'movie']
        
        for section in movie_sections:
            logger.info(f"Processing section: {section.title}")
            movies = section.all()
            
            for movie in movies:
                # Process movie data
                date_added = movie.addedAt if hasattr(movie, 'addedAt') else None
                file_path = movie.locations[0] if movie.locations else None
                file_size = os.path.getsize(file_path) if file_path and os.path.exists(file_path) else None
                
                # Find or create movie record
                db_movie = session.query(Movie).filter_by(plex_key=movie.key).first()
                if not db_movie:
                    db_movie = Movie(plex_key=movie.key)
                    session.add(db_movie)
                
                # Update movie data
                db_movie.title = movie.title
                db_movie.year = movie.year
                db_movie.date_added = date_added
                db_movie.duration = movie.duration if hasattr(movie, 'duration') else None
                db_movie.summary = movie.summary if hasattr(movie, 'summary') else None
                db_movie.content_rating = movie.contentRating if hasattr(movie, 'contentRating') else None
                db_movie.studio = movie.studio if hasattr(movie, 'studio') else None
                db_movie.file_path = file_path
                db_movie.file_size = file_size
                db_movie.last_updated = datetime.now()
                
                # Save to get ID for relationships
                session.flush()
                
                # Handle genres
                if hasattr(movie, 'genres') and movie.genres:
                    # Clear existing genres
                    db_movie.genres = []
                    
                    # Add genres
                    for genre in movie.genres:
                        db_genre = session.query(Genre).filter_by(name=genre.tag).first()
                        if not db_genre:
                            db_genre = Genre(name=genre.tag)
                            session.add(db_genre)
                            session.flush()
                        db_movie.genres.append(db_genre)
                
                # Handle ratings from Plex directly
                if hasattr(movie, 'rating') and movie.rating is not None:
                    # Plex user rating (out of 10)
                    plex_rating = insert(Rating.__table__).values(
                        movie_id=db_movie.id,
                        source='plex',
                        rating=float(movie.rating),
                        votes=1  # Default for user ratings
                    )
                    plex_rating = plex_rating.on_conflict_do_update(
                        index_elements=['id'],
                        set_={'rating': plex_rating.excluded.rating}
                    )
                    session.execute(plex_rating)
                
                # Check for audience rating
                if hasattr(movie, 'audienceRating') and movie.audienceRating is not None:
                    audience_rating = insert(Rating.__table__).values(
                        movie_id=db_movie.id,
                        source='audience',
                        rating=float(movie.audienceRating),
                        votes=0  # Unknown votes
                    )
                    audience_rating = audience_rating.on_conflict_do_update(
                        index_elements=['id'],
                        set_={'rating': audience_rating.excluded.rating}
                    )
                    session.execute(audience_rating)
                
                # Check for Rotten Tomatoes rating
                if hasattr(movie, 'ratingImage') and movie.ratingImage == 'rottentomatoes':
                    if hasattr(movie, 'rating') and movie.rating is not None:
                        rt_rating = insert(Rating.__table__).values(
                            movie_id=db_movie.id,
                            source='rottenTomatoes',
                            rating=float(movie.rating),
                            votes=0  # Unknown votes
                        )
                        rt_rating = rt_rating.on_conflict_do_update(
                            index_elements=['id'],
                            set_={'rating': rt_rating.excluded.rating}
                        )
                        session.execute(rt_rating)
                
                # Check for IMDb rating
                if hasattr(movie, 'ratingImage') and movie.ratingImage == 'imdb':
                    if hasattr(movie, 'rating') and movie.rating is not None:
                        imdb_rating = insert(Rating.__table__).values(
                            movie_id=db_movie.id,
                            source='imdb',
                            rating=float(movie.rating),
                            votes=0  # Unknown votes
                        )
                        imdb_rating = imdb_rating.on_conflict_do_update(
                            index_elements=['id'],
                            set_={'rating': imdb_rating.excluded.rating}
                        )
                        session.execute(imdb_rating)
                
                # Process play history
                if hasattr(movie, 'history'):
                    for item in movie.history():
                        if hasattr(item, 'viewedAt'):
                            played_at = item.viewedAt
                            
                            # Calculate percentage complete
                            percent_complete = calculate_percent_complete(movie, item)
                            
                            # Create history record
                            play_history = PlayHistory(
                                movie_id=db_movie.id,
                                account_id=item.accountID if hasattr(item, 'accountID') else None,
                                account_name=item.accountName if hasattr(item, 'accountName') else None,
                                device_name=item.deviceName if hasattr(item, 'deviceName') else None,
                                played_at=played_at,
                                percent_complete=percent_complete
                            )
                            session.add(play_history)
                
                # Commit each movie to avoid large transactions
                session.commit()
            
            logger.info(f"Completed processing section: {section.title}")
            
    except Exception as e:
        session.rollback()
        logger.error(f"Error processing movies: {e}")
        raise

def main():
    """Main function to run the ETL pipeline"""
    try:
        # Connect to Plex
        plex = connect_to_plex()
        
        # Create database engine
        engine = create_db_engine()
        
        # Set up database tables
        setup_database(engine)
        
        # Create session
        Session = sessionmaker(bind=engine)
        session = Session()
        
        try:
            # Process movies
            fetch_and_store_movies(plex, session)
        finally:
            # Close session
            session.close()
        
        logger.info("ETL pipeline completed successfully")
        
    except Exception as e:
        logger.error(f"ETL pipeline failed: {e}")

if __name__ == "__main__":
    main()