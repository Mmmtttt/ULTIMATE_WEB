<template>
  <div class="mine">
    <van-nav-bar title="我的" />
    
    <van-cell-group class="mine-menu">
      <van-cell title="导入漫画" icon="add-o" @click="showImportDialog = true" is-link />
      <van-cell title="标签管理" icon="tag-o" to="/tags" is-link />
      <van-cell title="清单管理" icon="list-o" is-link />
      <van-cell title="系统设置" icon="settings-o" is-link />
    </van-cell-group>
    
    <div class="about">
      <p class="version">版本 2.0.0</p>
      <p class="copyright">© 2026 自用漫画浏览网站</p>
    </div>
    
    <van-tabbar v-model="active" route>
      <van-tabbar-item icon="home-o" to="/">主页</van-tabbar-item>
      <van-tabbar-item icon="user-o" to="/mine">我的</van-tabbar-item>
    </van-tabbar>
    
    <van-popup v-model:show="showImportDialog" round position="center">
      <div class="import-dialog">
        <h3>导入漫画</h3>
        <van-field v-model="comicId" label="漫画ID" placeholder="请输入漫画ID" />
        <van-field v-model="comicTitle" label="漫画标题" placeholder="请输入漫画标题" />
        <div class="dialog-buttons">
          <van-button @click="showImportDialog = false">取消</van-button>
          <van-button type="primary" @click="importComic" :loading="importing">确定</van-button>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useComicStore } from '@/stores'
import { showSuccessToast, showFailToast } from 'vant'

const active = ref(1)
const showImportDialog = ref(false)
const comicId = ref('')
const comicTitle = ref('')
const importing = ref(false)

const comicStore = useComicStore()

const importComic = async () => {
  if (!comicId.value) {
    showFailToast('请输入漫画ID')
    return
  }
  
  importing.value = true
  
  try {
    const response = await comicStore.initComic({
      comic_id: comicId.value,
      title: comicTitle.value || comicId.value
    })
    
    if (response.code === 200) {
      showSuccessToast('导入成功')
      showImportDialog.value = false
      await comicStore.fetchComics()
      comicId.value = ''
      comicTitle.value = ''
    } else {
      showFailToast(response.msg || '导入失败')
    }
  } catch (error) {
    showFailToast('导入失败')
  } finally {
    importing.value = false
  }
}
</script>

<style scoped>
.mine {
  min-height: 100vh;
  background: #f5f5f5;
  padding-bottom: 50px;
}

.mine-menu {
  margin-top: 10px;
}

.about {
  text-align: center;
  padding: 40px 0;
  color: #999;
}

.version {
  font-size: 14px;
  margin-bottom: 8px;
}

.copyright {
  font-size: 12px;
}

.import-dialog {
  width: 300px;
  padding: 20px;
}

.import-dialog h3 {
  text-align: center;
  margin-bottom: 20px;
}

.dialog-buttons {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 20px;
}
</style>
