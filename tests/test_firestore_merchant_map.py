"""Tests for firestore_merchant_map using the in-memory mock client."""

import firestore_merchant_map as fmm
from tests.mock_firestore import MockFirestoreClient


def _setup_mock():
    """Install a fresh mock client and return it."""
    client = MockFirestoreClient()
    fmm.set_db(client)
    return client


class TestNormalizeMerchant:
    def test_basic(self):
        assert fmm.normalize_merchant("  Starbucks  ") == "starbucks"

    def test_punctuation_stripped(self):
        assert fmm.normalize_merchant("***UBER***") == "uber"

    def test_spaces_collapsed(self):
        assert fmm.normalize_merchant("Trader   Joe's") == "trader joe's"

    def test_empty(self):
        assert fmm.normalize_merchant("") == ""

    def test_none_like(self):
        assert fmm.normalize_merchant("") == ""


class TestLoadMap:
    def test_empty(self):
        _setup_mock()
        assert fmm.load_map() == {}

    def test_with_data(self):
        client = _setup_mock()
        col = client.collection("merchant_map")
        col.document("starbucks").set({"category": "🍽️ Dining Out"})
        col.document("uber").set({"category": "🚗 Transportation"})
        result = fmm.load_map()
        assert result == {
            "starbucks": "🍽️ Dining Out",
            "uber": "🚗 Transportation",
        }


class TestSaveMap:
    def test_save_and_load(self):
        _setup_mock()
        data = {
            "starbucks": "🍽️ Dining Out",
            "uber": "🚗 Transportation",
        }
        fmm.save_map(data)
        assert fmm.load_map() == data

    def test_save_overwrites(self):
        _setup_mock()
        fmm.save_map({"starbucks": "🍽️ Dining Out"})
        fmm.save_map({"uber": "🚗 Transportation"})
        result = fmm.load_map()
        assert "starbucks" not in result
        assert result["uber"] == "🚗 Transportation"

    def test_save_empty(self):
        _setup_mock()
        fmm.save_map({"starbucks": "🍽️ Dining Out"})
        fmm.save_map({})
        assert fmm.load_map() == {}


class TestUpdateMapping:
    def test_update_single(self):
        _setup_mock()
        fmm.update_mapping("Starbucks", "🍽️ Dining Out")
        result = fmm.load_map()
        assert result["starbucks"] == "🍽️ Dining Out"

    def test_update_overwrite(self):
        _setup_mock()
        fmm.update_mapping("Starbucks", "🍽️ Dining Out")
        fmm.update_mapping("Starbucks", "🔧 Other")
        result = fmm.load_map()
        assert result["starbucks"] == "🔧 Other"

    def test_update_empty_merchant_ignored(self):
        _setup_mock()
        fmm.update_mapping("", "🍽️ Dining Out")
        assert fmm.load_map() == {}
