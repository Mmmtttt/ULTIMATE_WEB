import unittest
import requests
import json

class TestComicAPI(unittest.TestCase):
    base_url = 'http://127.0.0.1:5000'
    
    @classmethod
    def setUpClass(cls):
        pass
    
    def test_health_check(self):
        """测试健康检查接口"""
        response = requests.get(f'{self.base_url}/health')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 200)
        self.assertEqual(data['data']['status'], 'ok')
        print('✓ 健康检查接口测试通过')
    
    def test_comic_list(self):
        """测试漫画列表接口"""
        response = requests.get(f'{self.base_url}/api/v1/comic/list')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 200)
        self.assertIsInstance(data['data'], list)
        self.assertGreaterEqual(len(data['data']), 1)
        
        if len(data['data']) > 0:
            comic = data['data'][0]
            self.assertIn('id', comic)
            self.assertIn('title', comic)
            self.assertIn('author', comic)
            self.assertIn('cover_path', comic)
            self.assertIn('total_page', comic)
            self.assertIn('current_page', comic)
            self.assertIn('tag_ids', comic)
        
        print(f'✓ 漫画列表接口测试通过，返回 {len(data["data"])} 个漫画')
    
    def test_comic_detail(self):
        """测试漫画详情接口"""
        comic_id = '1024707'
        response = requests.get(f'{self.base_url}/api/v1/comic/detail', params={'comic_id': comic_id})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 200)
        self.assertEqual(data['data']['id'], comic_id)
        
        self.assertIn('title', data['data'])
        self.assertIn('author', data['data'])
        self.assertIn('cover_path', data['data'])
        self.assertIn('total_page', data['data'])
        
        print('✓ 漫画详情接口测试通过')
    
    def test_comic_detail_invalid_id(self):
        """测试漫画详情接口 - 无效ID"""
        response = requests.get(f'{self.base_url}/api/v1/comic/detail', params={'comic_id': 'invalid_id'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 404)
        print('✓ 漫画详情接口无效ID测试通过')
    
    def test_comic_images(self):
        """测试图片列表接口"""
        comic_id = '1024707'
        response = requests.get(f'{self.base_url}/api/v1/comic/images', params={'comic_id': comic_id})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 200)
        self.assertIsInstance(data['data'], list)
        self.assertGreaterEqual(len(data['data']), 1)
        
        if len(data['data']) > 0:
            self.assertIsInstance(data['data'][0], str)
            self.assertTrue(len(data['data'][0]) > 0)
        
        print(f'✓ 图片列表接口测试通过，返回 {len(data["data"])} 张图片')
    
    def test_comic_image(self):
        """测试单张图片接口"""
        comic_id = '1024707'
        page_num = 1
        response = requests.get(f'{self.base_url}/api/v1/comic/image', params={'comic_id': comic_id, 'page_num': page_num})
        self.assertEqual(response.status_code, 200)
        self.assertIn('image', response.headers['Content-Type'])
        print('✓ 单张图片接口测试通过')
    
    def test_comic_progress_save(self):
        """测试进度保存接口"""
        comic_id = '1024707'
        current_page = 5
        response = requests.put(f'{self.base_url}/api/v1/comic/progress', json={
            'comic_id': comic_id,
            'current_page': current_page
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 200)
        self.assertEqual(data['data']['current_page'], current_page)
        print('✓ 进度保存接口测试通过')
    
    def test_comic_progress_invalid_data(self):
        """测试进度保存接口 - 无效数据"""
        response = requests.put(f'{self.base_url}/api/v1/comic/progress', json={
            'comic_id': 'invalid'
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 400)
        print('✓ 进度保存接口无效数据测试通过')
    
    def test_tags_list(self):
        """测试标签列表接口"""
        response = requests.get(f'{self.base_url}/api/v1/comic/tags')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 200)
        self.assertIsInstance(data['data'], list)
        print(f'✓ 标签列表接口测试通过，返回 {len(data["data"])} 个标签')
    
    def test_cover_image(self):
        """测试封面图片接口"""
        response = requests.get(f'{self.base_url}/static/cover/1024707.jpg')
        self.assertIn(response.status_code, [200, 304])
        print('✓ 封面图片接口测试通过')


class TestAPIIntegration(unittest.TestCase):
    """API集成测试"""
    base_url = 'http://127.0.0.1:5000'
    
    def test_full_reading_flow(self):
        """测试完整阅读流程"""
        comic_id = '1024707'
        
        response = requests.get(f'{self.base_url}/api/v1/comic/list')
        self.assertEqual(response.status_code, 200)
        
        response = requests.get(f'{self.base_url}/api/v1/comic/detail', params={'comic_id': comic_id})
        self.assertEqual(response.status_code, 200)
        
        response = requests.get(f'{self.base_url}/api/v1/comic/images', params={'comic_id': comic_id})
        self.assertEqual(response.status_code, 200)
        images = response.json()['data']
        
        if len(images) > 0:
            response = requests.get(f'{self.base_url}/api/v1/comic/image', params={'comic_id': comic_id, 'page_num': 1})
            self.assertEqual(response.status_code, 200)
        
        response = requests.put(f'{self.base_url}/api/v1/comic/progress', json={
            'comic_id': comic_id,
            'current_page': 10
        })
        self.assertEqual(response.status_code, 200)
        
        print('✓ 完整阅读流程测试通过')


if __name__ == '__main__':
    unittest.main(verbosity=2)
