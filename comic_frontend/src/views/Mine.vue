<template>
  <div class="mine">
    <van-nav-bar title="我的" />
    
    <van-cell-group class="mine-menu">
      <van-cell title="导入漫画" icon="add-o" @click="showImportDialog = true" />
      <van-cell title="标签管理" icon="tag-o" />
      <van-cell title="清单管理" icon="list-o" />
      <van-cell title="系统设置" icon="settings-o" />
    </van-cell-group>
    
    <div class="about">
      <p class="version">版本 1.0.0</p>
      <p class="copyright">© 2026 自用漫画浏览网站</p>
    </div>
    
    <van-tabbar v-model="active" route>
      <van-tabbar-item icon="home-o" to="/">主页</van-tabbar-item>
      <van-tabbar-item icon="user-o" to="/mine">我的</van-tabbar-item>
    </van-tabbar>
    
    <!-- 导入漫画弹窗 -->
    <van-popup v-model:show="showImportDialog" round position="center">
      <div class="import-dialog">
        <h3>导入漫画</h3>
        <van-field v-model="comicId" label="漫画ID" placeholder="请输入漫画ID" />
        <van-field v-model="comicTitle" label="漫画标题" placeholder="请输入漫画标题" />
        <div class="dialog-buttons">
          <van-button @click="showImportDialog = false">取消</van-button>
          <van-button type="primary" @click="importComic">确定</van-button>
        </div>
      </div>
    </van-popup>
    
    <!-- 导入结果提示 -->
    <van-toast v-model:show="showToast" :message="toastMessage" :type="toastType" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useComicStore } from '../store/modules/comic'
import { comicApi } from '../api/comic'

const active = ref(1)
const showImportDialog = ref(false)
const comicId = ref('')
const comicTitle = ref('')
const showToast = ref(false)
const toastMessage = ref('')
const toastType = ref('success')

const comicStore = useComicStore()

const importComic = async () => {
  if (!comicId.value) {
    toastMessage.value = '请输入漫画ID'
    toastType.value = 'fail'
    showToast.value = true
    return
  }
  
  try {
    const response = await comicApi.init({
      comic_id: comicId.value,
      title: comicTitle.value || comicId.value
    })
    
    toastMessage.value = '导入成功'
    toastType.value = 'success'
    showToast.value = true
    showImportDialog.value = false
    
    // 刷新漫画列表
    await comicStore.fetchComics()
    
    // 清空输入
    comicId.value = ''
    comicTitle.value = ''
  } catch (error) {
    toastMessage.value = error.message || '导入失败'
    toastType.value = 'fail'
    showToast.value = true
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
