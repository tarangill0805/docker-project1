import io
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from app import create_app

class WebsiteTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        root=Path(self.tmp.name)
        self.app=create_app({'TESTING':True,'SECRET_KEY':'test-only','DATABASE':str(root/'db.sqlite3'),'UPLOAD_FOLDER':str(root/'uploads')})
        self.client=self.app.test_client()
        self.runner=self.app.test_cli_runner()
        result=self.runner.invoke(args=['set-admin','--email','owner@example.com','--password','test-password-123'])
        self.assertEqual(result.exit_code,0,result.output)
    def tearDown(self):
        self.tmp.cleanup()
    def token(self,path='/'):
        page=self.client.get(path)
        return re.search(rb'name="csrf_token" value="([^"]+)"',page.data).group(1).decode()
    def login(self):
        t=self.token('/admin/login')
        return self.client.post('/admin/login',data={'csrf_token':t,'email':'owner@example.com','password':'test-password-123'})
    def rows(self,sql):
        with sqlite3.connect(self.app.config['DATABASE']) as conn:return conn.execute(sql).fetchall()
    def test_public_filters_and_details(self):
        self.assertEqual(self.client.get('/').status_code,200)
        page=self.client.get('/?mode=rent&city=Mohali&type=Apartment').data
        self.assertIn(b'Your everyday, reimagined',page)
        self.assertNotIn(b'A home with room to breathe</a>',page)
        self.assertIn(b'No matches yet',self.client.get('/?city=Nowhere').data)
        self.assertEqual(self.client.get('/properties/demo-villa').status_code,200)
        self.assertEqual(self.client.get('/properties/missing').status_code,404)
    def test_admin_security_and_reset(self):
        self.assertEqual(self.client.get('/admin').status_code,302)
        self.assertEqual(self.client.post('/admin/property/demo-villa/delete').status_code,400)
        token=self.token()
        self.assertEqual(self.client.post('/admin/property/demo-villa/delete',data={'csrf_token':token}).status_code,302)
        self.assertEqual(len(self.rows('SELECT * FROM properties')),5)
        self.assertEqual(self.login().status_code,302)
        self.assertIn(b'Owner dashboard',self.client.get('/admin').data)
        self.runner.invoke(args=['set-admin','--email','owner@example.com','--password','replacement-password'])
        self.assertEqual(self.client.get('/admin').status_code,302)
    def test_enquiry(self):
        t=self.token()
        data=dict(csrf_token=t,name='Test Buyer',phone='9876543210',email='buyer@example.com',message='A home in Mohali',property_id='demo-villa')
        self.assertEqual(self.client.post('/enquiry',data=data).status_code,302)
        self.assertEqual(len(self.rows('SELECT * FROM enquiries')),1)
        data['phone']='bad'
        self.assertEqual(self.client.post('/enquiry',data=data).status_code,400)
        self.assertEqual(len(self.rows('SELECT * FROM enquiries')),1)
    def test_property_crud_upload(self):
        self.login();t=self.token('/admin/property/new')
        image=io.BytesIO();Image.new('RGB',(20,20),'green').save(image,'PNG');image.seek(0)
        data=dict(csrf_token=t,title='<script>alert(1)</script>',city='Mohali',type='House',mode='buy',price='₹1 Cr',area='1200 sq ft',beds='3',description='A lovely house',photos=(image,'house.png'))
        r=self.client.post('/admin/property/new',data=data,content_type='multipart/form-data');self.assertEqual(r.status_code,302)
        row=self.rows("SELECT id,images FROM properties WHERE title LIKE '<script>%' ")[0]
        import json
        response=self.client.get(json.loads(row[1])[0]); self.assertEqual(response.status_code,200); response.close()
        page=self.client.get('/properties/'+row[0]);self.assertIn(b'&lt;script&gt;',page.data)
        data.pop('photos');data['title']='Updated house';data['images']='\n'.join(json.loads(row[1]))
        self.assertEqual(self.client.post('/admin/property/'+row[0]+'/edit',data=data).status_code,302)
        self.assertIn(b'Updated house',self.client.get('/properties/'+row[0]).data)
        self.assertEqual(self.client.post('/admin/property/'+row[0]+'/delete',data={'csrf_token':t}).status_code,302)
        self.assertEqual(self.client.get('/properties/'+row[0]).status_code,404)
    def test_reject_invalid_upload_and_url(self):
        self.login();t=self.token('/admin/property/new')
        data=dict(csrf_token=t,title='Test',city='Mohali',type='House',mode='buy',price='₹1 Cr',area='1200',beds='3',description='Test house',images='javascript:alert(1)')
        self.assertEqual(self.client.post('/admin/property/new',data=data).status_code,400)
        data['images']='';data['photos']=(io.BytesIO(b'not a picture'),'fake.jpg')
        self.assertEqual(self.client.post('/admin/property/new',data=data).status_code,400)

if __name__=='__main__':unittest.main()
