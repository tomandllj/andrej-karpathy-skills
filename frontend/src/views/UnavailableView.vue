<template>
  <!-- 中文：未登录或未知地址时的占位，不暴露登录 URI -->
  <div class="unavailable">
    <h1 class="title">页面不存在</h1>
    <p class="hint">请检查地址是否正确</p>
  </div>
</template>

<script setup>
/** 未授权或无效地址的统一提示页。 */
</script>

<style scoped>
.unavailable {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 32px 16px;
  background: var(--bg-page, #f8fafc);
  color: var(--text-body, #1e293b);
}
.title {
  margin: 0;
  font-size: 22px;
  letter-spacing: -0.02em;
  color: var(--text-title, #0f172a);
}
.hint {
  margin: 0;
  font-size: 14px;
  color: var(--text-muted, #64748b);
}
</style>
