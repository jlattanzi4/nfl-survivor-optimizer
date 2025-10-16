"""Cache manager for storing and retrieving data."""
import os
import json
import pickle
from datetime import datetime, timedelta
from typing import Any, Optional
import pandas as pd
import config


class CacheManager:
    """Manages caching of data to reduce API calls."""

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize cache manager.

        Args:
            cache_dir: Directory for cache files (defaults to config.CACHE_DIR)
        """
        self.cache_dir = cache_dir or config.CACHE_DIR

        # Create cache directory if it doesn't exist
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)

    def _get_cache_path(self, key: str, extension: str = 'pkl') -> str:
        """Get full path for cache file."""
        safe_key = key.replace('/', '_').replace('\\', '_')
        return os.path.join(self.cache_dir, f"{safe_key}.{extension}")

    def _get_metadata_path(self, key: str) -> str:
        """Get path for metadata file."""
        return self._get_cache_path(key, 'meta.json')

    def is_cache_valid(self, key: str, max_age_hours: Optional[float] = None) -> bool:
        """
        Check if cached data exists and is still valid.

        Args:
            key: Cache key
            max_age_hours: Maximum age in hours (defaults to config.CACHE_EXPIRY_HOURS)

        Returns:
            True if cache is valid, False otherwise
        """
        max_age_hours = max_age_hours or config.CACHE_EXPIRY_HOURS
        metadata_path = self._get_metadata_path(key)

        if not os.path.exists(metadata_path):
            return False

        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)

            cached_time = datetime.fromisoformat(metadata['timestamp'])
            age = datetime.now() - cached_time

            return age < timedelta(hours=max_age_hours)
        except Exception:
            return False

    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve data from cache.

        Args:
            key: Cache key

        Returns:
            Cached data or None if not found/invalid
        """
        if not self.is_cache_valid(key):
            return None

        cache_path = self._get_cache_path(key)

        try:
            with open(cache_path, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            print(f"Error loading cache: {e}")
            return None

    def set(self, key: str, data: Any) -> bool:
        """
        Store data in cache.

        Args:
            key: Cache key
            data: Data to cache

        Returns:
            True if successful, False otherwise
        """
        cache_path = self._get_cache_path(key)
        metadata_path = self._get_metadata_path(key)

        try:
            # Save data
            with open(cache_path, 'wb') as f:
                pickle.dump(data, f)

            # Save metadata
            metadata = {
                'timestamp': datetime.now().isoformat(),
                'key': key
            }
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f)

            return True
        except Exception as e:
            print(f"Error saving cache: {e}")
            return False

    def clear(self, key: Optional[str] = None) -> None:
        """
        Clear cache.

        Args:
            key: Specific key to clear (if None, clears all)
        """
        if key:
            # Clear specific key
            cache_path = self._get_cache_path(key)
            metadata_path = self._get_metadata_path(key)

            for path in [cache_path, metadata_path]:
                if os.path.exists(path):
                    os.remove(path)
        else:
            # Clear all cache
            for filename in os.listdir(self.cache_dir):
                filepath = os.path.join(self.cache_dir, filename)
                if os.path.isfile(filepath):
                    os.remove(filepath)

    def get_cache_info(self) -> dict:
        """
        Get information about cached items.

        Returns:
            Dictionary with cache statistics
        """
        items = []
        total_size = 0

        for filename in os.listdir(self.cache_dir):
            if filename.endswith('.pkl'):
                filepath = os.path.join(self.cache_dir, filename)
                size = os.path.getsize(filepath)
                total_size += size

                key = filename[:-4]  # Remove .pkl
                metadata_path = self._get_metadata_path(key)

                if os.path.exists(metadata_path):
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                    items.append({
                        'key': key,
                        'size': size,
                        'timestamp': metadata.get('timestamp', 'unknown')
                    })

        return {
            'total_items': len(items),
            'total_size_bytes': total_size,
            'items': items
        }


def test_cache():
    """Test cache functionality."""
    print("Testing Cache Manager")
    print("=" * 60)

    cache = CacheManager()

    # Test data
    test_data = pd.DataFrame({
        'team': ['Team A', 'Team B', 'Team C'],
        'win_prob': [0.75, 0.65, 0.55]
    })

    # Test set
    print("\nTesting cache.set()...")
    success = cache.set('test_data', test_data)
    print(f"Set result: {success}")

    # Test get
    print("\nTesting cache.get()...")
    retrieved = cache.get('test_data')
    print(f"Retrieved successfully: {retrieved is not None}")
    if retrieved is not None:
        print(retrieved)

    # Test is_valid
    print("\nTesting cache.is_cache_valid()...")
    is_valid = cache.is_cache_valid('test_data')
    print(f"Cache is valid: {is_valid}")

    # Test cache info
    print("\nCache info:")
    info = cache.get_cache_info()
    print(f"Total items: {info['total_items']}")
    print(f"Total size: {info['total_size_bytes']} bytes")

    # Test clear
    print("\nTesting cache.clear()...")
    cache.clear('test_data')
    is_valid_after = cache.is_cache_valid('test_data')
    print(f"Cache valid after clear: {is_valid_after}")


if __name__ == "__main__":
    test_cache()
