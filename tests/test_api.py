import unittest
import requests
import json
import time

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
        
        if len(data['data']) > 0:
            comic = data['data'][0]
            self.assertIn('id', comic)
            self.assertIn('title', comic)
            self.assertIn('author', comic)
            self.assertIn('cover_path', comic)
            self.assertIn('total_page', comic)
            self.assertIn('current_page', comic)
            self.assertIn('tag_ids', comic)
            self.assertIn('tags', comic)
            self.assertIn('score', comic)
        
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
        self.assertIn('tags', data['data'])
        self.assertIn('preview_images', data['data'])
        self.assertIn('preview_pages', data['data'])
        
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


class TestTagAPI(unittest.TestCase):
    """标签管理接口测试"""
    base_url = 'http://127.0.0.1:5000'
    test_tag_id = None
    
    def test_01_tag_add(self):
        """测试新增标签接口"""
        tag_name = f'测试标签_{int(time.time())}'
        response = requests.post(f'{self.base_url}/api/v1/tag/add', json={
            'tag_name': tag_name
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 200)
        self.assertIn('id', data['data'])
        self.assertEqual(data['data']['name'], tag_name)
        TestTagAPI.test_tag_id = data['data']['id']
        print(f'✓ 新增标签接口测试通过，标签ID: {TestTagAPI.test_tag_id}')
    
    def test_02_tag_list(self):
        """测试标签列表接口"""
        response = requests.get(f'{self.base_url}/api/v1/tag/list')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 200)
        self.assertIsInstance(data['data'], list)
        
        if len(data['data']) > 0:
            tag = data['data'][0]
            self.assertIn('id', tag)
            self.assertIn('name', tag)
            self.assertIn('comic_count', tag)
        
        print(f'✓ 标签列表接口测试通过，返回 {len(data["data"])} 个标签')
    
    def test_03_tag_edit(self):
        """测试编辑标签接口"""
        if not TestTagAPI.test_tag_id:
            self.skipTest('没有可用的测试标签ID')
        
        new_name = f'编辑后标签_{int(time.time())}'
        response = requests.put(f'{self.base_url}/api/v1/tag/edit', json={
            'tag_id': TestTagAPI.test_tag_id,
            'tag_name': new_name
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 200)
        self.assertEqual(data['data']['name'], new_name)
        print('✓ 编辑标签接口测试通过')
    
    def test_04_tag_add_duplicate(self):
        """测试新增重复标签"""
        response = requests.get(f'{self.base_url}/api/v1/tag/list')
        if len(response.json()['data']) == 0:
            self.skipTest('没有可用的标签')
        
        existing_tag = response.json()['data'][0]
        response = requests.post(f'{self.base_url}/api/v1/tag/add', json={
            'tag_name': existing_tag['name']
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 400)
        print('✓ 重复标签测试通过')


class TestComicScoreAPI(unittest.TestCase):
    """漫画评分接口测试"""
    base_url = 'http://127.0.0.1:5000'
    comic_id = '1024707'
    
    def test_01_update_score(self):
        """测试更新评分接口"""
        response = requests.put(f'{self.base_url}/api/v1/comic/score', json={
            'comic_id': self.comic_id,
            'score': 8.5
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 200)
        self.assertEqual(data['data']['score'], 8.5)
        print('✓ 更新评分接口测试通过')
    
    def test_02_update_score_invalid(self):
        """测试更新评分接口 - 无效评分"""
        response = requests.put(f'{self.base_url}/api/v1/comic/score', json={
            'comic_id': self.comic_id,
            'score': 15
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 400)
        print('✓ 无效评分测试通过')
    
    def test_03_update_score_precision(self):
        """测试更新评分接口 - 0.5精度"""
        response = requests.put(f'{self.base_url}/api/v1/comic/score', json={
            'comic_id': self.comic_id,
            'score': 7.5
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 200)
        self.assertEqual(data['data']['score'], 7.5)
        print('✓ 0.5精度评分测试通过')


class TestComicSearchAPI(unittest.TestCase):
    """漫画搜索接口测试"""
    base_url = 'http://127.0.0.1:5000'
    
    def test_search_by_id(self):
        """测试按ID搜索"""
        response = requests.get(f'{self.base_url}/api/v1/comic/search', params={'keyword': '1024707'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 200)
        self.assertIsInstance(data['data'], list)
        if len(data['data']) > 0:
            self.assertEqual(data['data'][0]['id'], '1024707')
        print(f'✓ 按ID搜索测试通过，结果数量: {len(data["data"])}')
    
    def test_search_by_title(self):
        """测试按标题搜索"""
        response = requests.get(f'{self.base_url}/api/v1/comic/search', params={'keyword': '漫画'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 200)
        self.assertIsInstance(data['data'], list)
        print(f'✓ 按标题搜索测试通过，结果数量: {len(data["data"])}')
    
    def test_search_empty_keyword(self):
        """测试空关键词搜索"""
        response = requests.get(f'{self.base_url}/api/v1/comic/search', params={'keyword': ''})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 400)
        print('✓ 空关键词搜索测试通过')


class TestComicFilterAPI(unittest.TestCase):
    """漫画筛选接口测试"""
    base_url = 'http://127.0.0.1:5000'
    
    def test_filter_no_params(self):
        """测试无参数筛选"""
        response = requests.get(f'{self.base_url}/api/v1/comic/filter')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 200)
        self.assertIsInstance(data['data'], list)
        print(f'✓ 无参数筛选测试通过，结果数量: {len(data["data"])}')
    
    def test_filter_with_include_tags(self):
        """测试包含标签筛选"""
        response = requests.get(f'{self.base_url}/api/v1/tag/list')
        if len(response.json()['data']) == 0:
            self.skipTest('没有可用的标签')
        
        tag_id = response.json()['data'][0]['id']
        response = requests.get(f'{self.base_url}/api/v1/comic/filter', params={'include_tag_ids': tag_id})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 200)
        self.assertIsInstance(data['data'], list)
        print(f'✓ 包含标签筛选测试通过，结果数量: {len(data["data"])}')


class TestComicEditAPI(unittest.TestCase):
    """漫画编辑接口测试"""
    base_url = 'http://127.0.0.1:5000'
    comic_id = '1024707'
    
    def test_edit_comic_meta(self):
        """测试编辑漫画元数据"""
        response = requests.put(f'{self.base_url}/api/v1/comic/edit', json={
            'comic_id': self.comic_id,
            'title': '测试标题',
            'author': '测试作者',
            'desc': '测试简介'
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['code'], 200)
        self.assertEqual(data['data']['title'], '测试标题')
        self.assertEqual(data['data']['author'], '测试作者')
        print('✓ 编辑漫画元数据测试通过')


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
    
    def test_tag_management_flow(self):
        """测试标签管理完整流程"""
        tag_name = f'流程测试标签_{int(time.time())}'
        
        response = requests.post(f'{self.base_url}/api/v1/tag/add', json={'tag_name': tag_name})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['code'], 200)
        tag_id = response.json()['data']['id']
        
        response = requests.put(f'{self.base_url}/api/v1/comic/tag/bind', json={
            'comic_id': '1024707',
            'tag_id_list': [tag_id]
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['code'], 200)
        
        response = requests.get(f'{self.base_url}/api/v1/comic/detail', params={'comic_id': '1024707'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(tag_id, response.json()['data']['tag_ids'])
        
        response = requests.delete(f'{self.base_url}/api/v1/tag/delete', json={'tag_id': tag_id})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['code'], 200)
        
        print('✓ 标签管理完整流程测试通过')


if __name__ == '__main__':
    unittest.main(verbosity=2)
