import unittest
import requests
import json

class TestComicAPI(unittest.TestCase):
    base_url = 'http://127.0.0.1:5000'
    
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
        # 验证至少有3个漫画
        self.assertGreaterEqual(len(data['data']), 3)
        print(f'✓ 漫画列表接口测试通过，返回 {len(data["data"])} 个漫画')
    
    def test_comic_detail(self):
        """测试漫画详情接口"""
        comic_id = '1024707'
        response = requests.get(f'{self.base_url}/api/v1/comic/detail', params={'comic_id': comic_id})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 200)
        self.assertEqual(data['data']['id'], comic_id)
        print(f'✓ 漫画详情接口测试通过')
    
    def test_comic_images(self):
        """测试图片列表接口"""
        comic_id = '1024707'
        response = requests.get(f'{self.base_url}/api/v1/comic/images', params={'comic_id': comic_id})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 200)
        self.assertIsInstance(data['data'], list)
        # 验证至少有100张图片
        self.assertGreaterEqual(len(data['data']), 100)
        print(f'✓ 图片列表接口测试通过，返回 {len(data["data"])} 张图片')
    
    def test_comic_image(self):
        """测试单张图片接口"""
        comic_id = '1024707'
        page_num = 1
        response = requests.get(f'{self.base_url}/api/v1/comic/image', params={'comic_id': comic_id, 'page_num': page_num})
        self.assertEqual(response.status_code, 200)
        self.assertIn('image', response.headers['Content-Type'])
        print(f'✓ 单张图片接口测试通过')
    
    def test_comic_progress(self):
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
        print(f'✓ 进度保存接口测试通过')

if __name__ == '__main__':
    unittest.main()
