<template>
  <!-- 中文：只缓存首页。从文档返回时组件还在，选中的文件夹不会丢。 -->
  <router-view v-slot="{ Component }">
    <keep-alive include="HomeView">
      <component :is="Component" />
    </keep-alive>
  </router-view>
</template>
