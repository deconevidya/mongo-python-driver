import datetime
import uuid

import pymongo

from bson import BSON
from bson.binary import JAVA_LEGACY
from bson.codec_options import CodecOptions
from bson.raw_bson import RawBSONDocument
from test import client_context, unittest, pair


class TestRawBSONDocument(unittest.TestCase):

    # {u'_id': ObjectId('556df68b6e32ab21a95e0785'),
    #  u'name': u'Sherlock',
    #  u'addresses': [{u'street': u'Baker Street'}]}
    bson_string = (
        b'Z\x00\x00\x00\x07_id\x00Um\xf6\x8bn2\xab!\xa9^\x07\x85\x02name\x00\t'
        b'\x00\x00\x00Sherlock\x00\x04addresses\x00&\x00\x00\x00\x030\x00\x1e'
        b'\x00\x00\x00\x02street\x00\r\x00\x00\x00Baker Street\x00\x00\x00\x00'
    )
    document = RawBSONDocument(bson_string)

    def tearDown(self):
        if client_context.connected:
            client_context.client.pymongo_test.test_raw.drop()

    def test_decode(self):
        self.assertEqual('Sherlock', self.document['name'])
        first_address = self.document['addresses'][0]
        self.assertIsInstance(first_address, RawBSONDocument)
        self.assertEqual('Baker Street', first_address['street'])

    def test_raw(self):
        self.assertEqual(self.bson_string, self.document.raw)

    @client_context.require_connection
    def test_round_trip(self):
        client = pymongo.MongoClient(pair, document_class=RawBSONDocument)
        client.pymongo_test.test_raw.insert_one(self.document)
        result = client.pymongo_test.test_raw.find_one(self.document['_id'])
        self.assertIsInstance(result, RawBSONDocument)
        self.assertEqual(dict(self.document.items()), dict(result.items()))

    def test_with_codec_options(self):
        # {u'date': datetime.datetime(2015, 6, 3, 18, 40, 50, 826000),
        #  u'_id': UUID('026fab8f-975f-4965-9fbf-85ad874c60ff')}
        # encoded with JAVA_LEGACY uuid representation.
        bson_string = (
            b'-\x00\x00\x00\x05_id\x00\x10\x00\x00\x00\x03eI_\x97\x8f\xabo\x02'
            b'\xff`L\x87\xad\x85\xbf\x9f\tdate\x00\x8a\xd6\xb9\xbaM'
            b'\x01\x00\x00\x00'
        )
        document = RawBSONDocument(
            bson_string,
            codec_options=CodecOptions(uuid_representation=JAVA_LEGACY))

        self.assertEqual(uuid.UUID('026fab8f-975f-4965-9fbf-85ad874c60ff'),
                         document['_id'])

    @client_context.require_connection
    def test_round_trip_codec_options(self):
        doc = {
            'date': datetime.datetime(2015, 6, 3, 18, 40, 50, 826000),
            '_id': uuid.UUID('026fab8f-975f-4965-9fbf-85ad874c60ff')
        }
        db = pymongo.MongoClient(pair).pymongo_test
        coll = db.get_collection(
            'test_raw',
            codec_options=CodecOptions(uuid_representation=JAVA_LEGACY))
        coll.insert_one(doc)
        raw_java_legacy = CodecOptions(uuid_representation=JAVA_LEGACY,
                                       document_class=RawBSONDocument)
        coll = db.get_collection('test_raw', codec_options=raw_java_legacy)
        self.assertEqual(
            RawBSONDocument(BSON.encode(doc, codec_options=raw_java_legacy)),
            coll.find_one())

    @client_context.require_connection
    def test_raw_bson_document_embedded(self):
        doc = {'embedded': self.document}
        db = client_context.client.pymongo_test
        db.test_raw.insert_one(doc)
        result = db.test_raw.find_one()
        self.assertEqual(BSON(self.document.raw).decode(), result['embedded'])

        # Make sure that CodecOptions are preserved.
        # {'embedded': [
        #   {u'date': datetime.datetime(2015, 6, 3, 18, 40, 50, 826000),
        #    u'_id': UUID('026fab8f-975f-4965-9fbf-85ad874c60ff')}
        # ]}
        # encoded with JAVA_LEGACY uuid representation.
        bson_string = (
            b'D\x00\x00\x00\x04embedded\x005\x00\x00\x00\x030\x00-\x00\x00\x00'
            b'\tdate\x00\x8a\xd6\xb9\xbaM\x01\x00\x00\x05_id\x00\x10\x00\x00'
            b'\x00\x03eI_\x97\x8f\xabo\x02\xff`L\x87\xad\x85\xbf\x9f\x00\x00'
            b'\x00'
        )
        rbd = RawBSONDocument(
            bson_string,
            codec_options=CodecOptions(uuid_representation=JAVA_LEGACY))

        db.test_raw.drop()
        db.test_raw.insert_one(rbd)
        result = db.get_collection('test_raw', codec_options=CodecOptions(
            uuid_representation=JAVA_LEGACY)).find_one()
        self.assertEqual(rbd['embedded'][0]['_id'],
                         result['embedded'][0]['_id'])
