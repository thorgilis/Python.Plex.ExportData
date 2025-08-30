import os
import logging
from datetime import datetime
from plexapi.server import PlexServer
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
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
DB_PASS = os.getenv('DB_PASSWORD')
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
    if not DB_PASS:
        logger.error("DB_PASSWORD environment variable not set")
        raise ValueError("DB_PASSWORD environment variable not set")
    
    connection_string = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_engine(connection_string)
    logger.info("Created SQLAlchemy engine for PostgreSQL database")
    return engine

def setup_database(engine):
    """Create necessary tables in a new schema and return the schema name"""
    schema_name = f"swap_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    with engine.begin() as conn:
        # Create new schema for this run
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{schema_name}"'))
        # Direct all unqualified object creation to the new schema
        conn.execute(text(f'SET search_path TO "{schema_name}"'))
        # Create tables in the new schema
        Base.metadata.create_all(bind=conn)
    logger.info(f"Database schema set up successfully in schema: {schema_name}")
    return schema_name

def finalize_swap(engine, new_schema_name):
    """Drop old public tables and move new schema tables to public (KISS swap)."""
    # Order matters for dropping to avoid FK issues if CASCADE isn't used.
    table_names = [
        'movie_genres',
        'ratings',
        'play_history',
        'genres',
        'movies',
    ]
    with engine.begin() as conn:
        # Drop old public tables if they exist
        for tbl in table_names:
            conn.execute(text(f'DROP TABLE IF EXISTS public."{tbl}" CASCADE'))
        # Move new tables from the staging schema to public
        for tbl in table_names:
            conn.execute(text(f'ALTER TABLE "{new_schema_name}"."{tbl}" SET SCHEMA public'))
        # Optionally drop the now-empty staging schema
        conn.execute(text(f'DROP SCHEMA IF EXISTS "{new_schema_name}"'))
    logger.info(f"Swapped in tables from schema {new_schema_name} to public")

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
        plex_users = {}
        for user in plex.myPlexAccount().users():
            plex_users[user.id] = user.username
        
        # Also add the owner account
        plex_users[1] = 'Me'
    
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
                if hasattr(movie, 'ratingImage') and movie.ratingImage and 'rottentomatoes' in str(movie.ratingImage).lower():
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
                
                # Process play history (dedupe before insert)
                if hasattr(movie, 'history'):
                    # Build a set of existing keys to avoid inserting duplicates already in DB
                    existing_keys = set()
                    try:
                        existing_rows = session.query(PlayHistory).filter_by(movie_id=db_movie.id).all()
                        for row in existing_rows:
                            normalized_dt = row.played_at.replace(hour=0, minute=0, second=0, microsecond=0) if row.played_at else None
                            existing_keys.add((row.account_id, row.device_name, normalized_dt))
                    except Exception:
                        existing_keys = set()

                    # Collect and dedupe in-memory by (account_id, device_name, played_at@midnight)
                    deduped = {}
                    for item in movie.history():
                        if hasattr(item, 'viewedAt') and item.viewedAt:
                            played_at = item.viewedAt.replace(hour=0, minute=0, second=0, microsecond=0)
                            accId = item.accountID if hasattr(item, 'accountID') else None
                            accName = plex_users.get(accId, 'Unknown')
                            deviceName = item.deviceName if hasattr(item, 'deviceName') else None
                            key = (accId, deviceName, played_at)

                            percent_complete = calculate_percent_complete(movie, item)

                            if key in deduped:
                                if percent_complete > deduped[key]['percent_complete']:
                                    deduped[key]['percent_complete'] = percent_complete
                            else:
                                deduped[key] = {
                                    'account_id': accId,
                                    'account_name': accName,
                                    'device_name': deviceName,
                                    'played_at': played_at,
                                    'percent_complete': percent_complete
                                }

                    # Insert only the new, deduped history rows
                    for key, h in deduped.items():
                        if key in existing_keys:
                            continue
                        play_history = PlayHistory(
                            movie_id=db_movie.id,
                            account_id=h['account_id'],
                            account_name=h['account_name'],
                            device_name=h['device_name'],
                            played_at=h['played_at'],
                            percent_complete=h['percent_complete']
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

        plex.sessions()
        
        # Create database engine
        engine = create_db_engine()
        
        # Set up database tables in a new schema for this run
        new_schema = setup_database(engine)
        
        # Create session
        Session = sessionmaker(bind=engine)
        session = Session()
        
        try:
            # Ensure inserts go to the new schema during this session
            session.execute(text(f'SET search_path TO "{new_schema}"'))
            # Process movies (into staging schema)
            fetch_and_store_movies(plex, session)
        finally:
            # Close session
            session.close()
        
        # Swap in new tables and drop the staging schema
        finalize_swap(engine, new_schema)

        logger.info("ETL pipeline completed successfully")
        
    except Exception as e:
        logger.error(f"ETL pipeline failed: {e}")

if __name__ == "__main__":
    main()