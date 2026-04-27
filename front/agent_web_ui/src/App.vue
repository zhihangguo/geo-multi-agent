<template>
  <div class="app-container">
    <!-- 登录页面 -->
    <div v-if="!isLoggedIn" class="login-container">
      <div class="login-form">
        <div class="its-logo-flat login-logo">
            <img src="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='64' height='64' viewBox='0 0 64 64' fill='none'><rect width='64' height='64' rx='14' fill='%23101F2F'/><path d='M16 40L32 16L48 40H16Z' fill='%2359D3FF'/><circle cx='32' cy='44' r='6' fill='%23F4B740'/></svg>" alt="GeoAssist Nova Logo" width="60" height="60"/>
          </div>
        <h1 class="login-title">GeoAssist Nova 多智能体协作平台</h1>
        <div class="login-input-group">
          <label for="username">用户名</label>
          <input 
            id="username"
            v-model="username"
            type="text"
            placeholder="请输入用户名"
            @keyup.enter="handleLogin"
          />
        </div>
        <div class="login-input-group">
          <label for="password">密码</label>
          <input 
            id="password"
            v-model="password"
            type="password"
            placeholder="请输入密码"
            @keyup.enter="handleLogin"
          />
        </div>
        <div v-if="loginError" class="login-error">
          {{ loginError }}
        </div>
        <button class="login-button btn-primary" @click="handleLogin">
          登录
        </button>
        <div class="login-hint">
          <p>体验账号：admin / 123456</p>
        </div>
        <div class="login-toggle">
          <span>还没有账号？</span>
          <a href="#" @click.prevent="showRegister = true">立即注册</a>
        </div>
        <div class="login-feature-section">
          <h2>GeoAssist Nova 能力速览</h2>
          <ul>
            <li>多智能体协作：任务拆解、流程编排与可追溯输出</li>
            <li>地学知识联动：文献、图谱、野外记录一站式汇聚</li>
            <li>现场决策支持：路线规划、补给安排、风险提示</li>
          </ul>
          <div class="login-screenshot-grid">
            <div class="screenshot-card">
              <span>协作面板预览</span>
            </div>
            <div class="screenshot-card">
              <span>任务流监控预览</span>
            </div>
            <div class="screenshot-card">
              <span>情境报告预览</span>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- 注册表单覆盖层 -->
        <div v-if="showRegister" class="register-overlay">
          <div class="register-form">
            <h2 class="register-title">注册新账号</h2>
            <div class="login-input-group">
              <label for="reg-username">用户名</label>
              <input id="reg-username" v-model="regUsername" type="text" placeholder="至少2个字符" @keyup.enter="handleRegister" />
            </div>
            <div class="login-input-group">
              <label for="reg-displayname">显示名称（可选）</label>
              <input id="reg-displayname" v-model="regDisplayName" type="text" placeholder="显示名称" @keyup.enter="handleRegister" />
            </div>
            <div class="login-input-group">
              <label for="reg-password">密码</label>
              <input id="reg-password" v-model="regPassword" type="password" placeholder="至少6个字符" @keyup.enter="handleRegister" />
            </div>
            <div class="login-input-group">
              <label for="reg-password-confirm">确认密码</label>
              <input id="reg-password-confirm" v-model="regPasswordConfirm" type="password" placeholder="再次输入密码" @keyup.enter="handleRegister" />
            </div>
            <div v-if="registerError" class="login-error">{{ registerError }}</div>
            <div v-if="registerSuccess" class="login-success">{{ registerSuccess }}</div>
            <button class="login-button btn-primary" @click="handleRegister">注册</button>
            <div class="login-toggle">
              <span>已有账号？</span>
              <a href="#" @click.prevent="showRegister = false">返回登录</a>
            </div>
          </div>
        </div>
    <!-- 主界面（登录后显示） -->
    <template v-else>
      <!-- 移除header部分，将用户信息移到结果框右上角 -->
      
      <div class="main-content">
        <!-- 左侧历史会话列表 - 可展开收起 -->
        <div class="sidebar-wrapper">
          <!-- 侧边栏内容 -->
          <div class="sidebar-content" :class="{ 'expanded': isSidebarExpanded }">
            <!-- 扁平化Logo和ITS标题 -->
            <div class="app-branding">
              <!-- 扁平风格的Logo -->
              <div class="its-logo-flat">
                <img src="data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='64' height='64' viewBox='0 0 64 64' fill='none'><rect width='64' height='64' rx='14' fill='%23101F2F'/><path d='M16 40L32 16L48 40H16Z' fill='%2359D3FF'/><circle cx='32' cy='44' r='6' fill='%23F4B740'/></svg>" alt="GeoAssist Nova Logo" width="40" height="40"/>
              </div>
              
              <!-- 标题 - 仅在展开状态显示 -->
              <!-- 已注释掉ITS文本显示 -->
              <!-- <div v-show="isSidebarExpanded" class="sidebar-text-content">
                <h1 class="its-title">ITS</h1>
              </div> -->
              
              <!-- 侧边栏展开/收起按钮 - 与logo水平对齐 -->
              <button
                class="toggle-sidebar-btn"
                @click="toggleSidebar"
                :title="isSidebarExpanded ? '收起侧边栏' : '展开侧边栏'"
              >
                <span v-if="isSidebarExpanded">◀</span>
                <span v-else>▶</span>
              </button>
            </div>
            
            <!-- 新建会话按钮 - 放到logo下方并左右拉伸 -->
            <div class="session-button-container" v-show="isSidebarExpanded">
              <a href="/" class="new-chat-btn" @click.prevent="createNewSession">
                <span class="icon">
                  <svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" role="img" style="" width="20" height="20" viewBox="0 0 1024 1024" name="AddConversation" class="iconify new-icon" data-v-9f34fd85="">
                    <path d="M475.136 561.152v89.74336c0 20.56192 16.50688 37.23264 36.864 37.23264s36.864-16.67072 36.864-37.23264v-89.7024h89.7024c20.60288 0 37.2736-16.54784 37.2736-36.864 0-20.39808-16.67072-36.864-37.2736-36.864H548.864V397.63968A37.0688 37.0688 0 0 0 512 360.448c-20.35712 0-36.864 16.67072-36.864 37.2736v89.7024H385.4336a37.0688 37.0688 0 0 0-37.2736 36.864c0 20.35712 16.67072 36.864 37.2736 36.864h89.7024z" fill="currentColor"></path>
                    <path d="M512 118.784c-223.96928 0-405.504 181.57568-405.504 405.504 0 78.76608 22.44608 152.3712 61.35808 214.6304l-44.27776 105.6768a61.44 61.44 0 0 0 56.68864 85.1968H512c223.92832 0 405.504-181.53472 405.504-405.504 0-223.92832-181.57568-405.504-405.504-405.504z m-331.776 405.504a331.776 331.776 0 1 1 331.73504 331.776H198.656l52.59264-125.5424-11.59168-16.62976A330.09664 330.09664 0 0 1 180.224 524.288z" fill="currentColor"></path>
                  </svg>
                </span>
                <span class="text">新建会话</span>
                <span class="shortcut">
                  <span class="key">Ctrl</span>
                  <span>+</span>
                  <span class="key">K</span>
                </span>
              </a>
            </div>
            
            <!-- 导航栏 -->
            <div class="navigation-container" v-show="isSidebarExpanded">
              <div class="navigation-item" :class="{ 'selected': selectedNavItem === 'knowledge' }" @click="handleKnowledgeBase">
                <svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" fill="none" viewBox="0 0 24 24" class="nav-icon">
                  <path fill="currentColor" fill-rule="evenodd" d="M3.75 7h16.563c0 .48-.007 1.933-.016 3.685.703.172 1.36.458 1.953.837V5.937a2 2 0 0 0-2-2h-6.227a3 3 0 0 1-1.015-.176L9.992 2.677A3 3 0 0 0 8.979 2.5h-5.23a2 2 0 0 0-1.999 2v14.548a2 2 0 0 0 2 2h10.31a6.5 6.5 0 0 1-1.312-2H3.75S3.742 8.5 3.75 7m15.002 14.5a.514.514 0 0 0 .512-.454c.24-1.433.451-2.169.907-2.625.454-.455 1.186-.666 2.611-.907a.513.513 0 0 0-.002-1.026c-1.423-.241-2.155-.453-2.61-.908-.455-.457-.666-1.191-.906-2.622a.514.514 0 0 0-.512-.458.52.52 0 0 0-.515.456c-.24 1.432-.452 2.167-.907 2.624-.454.455-1.185.667-2.607.909a.514.514 0 0 0-.473.513.52.52 0 0 0 .47.512c1.425.24 2.157.447 2.61.9.455.454.666 1.19.907 2.634a.52.52 0 0 0 .515.452" clip-rule="evenodd"></path>
                </svg>
                <span class="nav-text">知识仓智搜</span>
              </div>
              <div class="navigation-item" :class="{ 'selected': selectedNavItem === 'service' }" @click="handleServiceStation">
                <svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" fill="none" viewBox="0 0 24 24" class="nav-icon">
                  <path fill="currentColor" fill-rule="evenodd" d="M12 20.571a8.5 8.5 0 0 1 2.5-6.08c1.43-1.429 3.5-2.49 6.071-2.491-2.571.002-4.617-1.075-6.05-2.508S12 6 12 3.428C12 6 10.954 8.095 9.517 9.532 8.081 10.968 6 12 3.428 12a8.52 8.52 0 0 1 6.082 2.516c1.43 1.43 2.487 3.484 2.49 6.055m-9.853-7.314c3.485.588 5.053 1.331 6.163 2.44s1.847 2.667 2.435 6.198c.105.627.603 1.105 1.26 1.105.664 0 1.156-.479 1.25-1.11.588-3.502 1.329-5.085 2.441-6.2 1.111-1.114 2.677-1.845 6.16-2.433.638-.075 1.144-.586 1.144-1.253 0-.668-.5-1.188-1.147-1.254-3.481-.59-5.026-1.347-6.137-2.46-1.112-1.115-1.872-2.674-2.46-6.171C13.16 1.482 12.671 1 12.003 1c-.66 0-1.155.481-1.259 1.114-.588 3.5-1.323 5.087-2.435 6.203C7.2 9.43 5.632 10.159 2.156 10.75 1.503 10.816 1 11.333 1 12.004c0 .68.52 1.17 1.147 1.253" clip-rule="evenodd"></path>
                </svg>
                <span class="nav-text">服务枢纽</span>
              </div>
              <div class="navigation-item" :class="{ 'selected': selectedNavItem === 'network' }" @click="handleNetworkSearch">
                <svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" fill="none" viewBox="0 0 24 24" class="nav-icon">
                  <path fill="currentColor" fill-rule="evenodd" d="M11 4a7 7 0 1 0 6.993 7.328c-.039-.53-.586-.93-1.131-.891a5.5 5.5 0 1 1-6.203-6.203.75.75 0 0 0-1.317-.63C4.617 5.458 2.75 8.425 2.75 12c0 4.418 3.582 8 8 8s8-3.582 8-8a7.961 7.961 0 0 0-1.996-5.38" clip-rule="evenodd"></path>
                  <path stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="m21 21-3.5-3.5"></path>
                </svg>
                <span class="nav-text">全网雷达</span>
              </div>
              

            </div>

            <!-- 历史会话列表 - 直接显示，不需要点击导航项 -->
            <div v-show="isSidebarExpanded" class="sidebar-main">
              <div class="sessions-list-header">
                <span class="sessions-title">历史会话</span>
              </div>
              <div class="sessions-list">
                <div class="session-search-wrap">
                  <input
                    v-model="sessionSearchKeyword"
                    class="session-search-input"
                    type="text"
                    placeholder="搜索会话"
                  />
                </div>
                <div v-if="isLoadingSessions" class="loading-sessions">
                  加载历史对话中...
                </div>
                <div v-else-if="filteredSessions.length === 0" class="no-sessions">
                  暂无匹配会话
                </div>
                <template v-else>
                  <div v-for="group in groupedSessions" :key="group.key" class="session-group">
                    <div class="session-group-title">{{ group.label }}</div>
                    <div
                      v-for="session in group.items"
                      :key="session.session_id"
                      :class="['session-item', { 'selected': session.session_id === selectedSessionId }]"
                      @click="selectSession(session.session_id)"
                    >
                      <div class="session-info">
                        <div style="display: flex; align-items: center; gap: 8px; width: 100%; position: relative; overflow: visible;">
                          <img alt="会话" src="//lf-flow-web-cdn.doubao.com/obj/flow-doubao/doubao/chat/static/image/default.light.2ea4b2b4.png" class="session-icon" style="width: 24px; height: 24px; border-radius: 4px; object-fit: cover; flex-shrink: 0;">
                          <div class="session-preview">{{ sessionDisplayName(session) }}</div>
                          <span v-if="sessionMeta[session.session_id]?.pinned" class="session-pin-mark">📌</span>
                          <button
                            class="session-menu-trigger"
                            title="会话操作"
                            @click.stop="toggleSessionMenu(session.session_id)"
                          >
                            ⋯
                          </button>
                          <div
                            v-if="openedSessionMenuId === session.session_id"
                            class="session-menu"
                            @click.stop
                          >
                            <button class="session-menu-item" @click="togglePinSession(session.session_id)">
                              {{ sessionMeta[session.session_id]?.pinned ? '取消置顶' : '置顶会话' }}
                            </button>
                            <button class="session-menu-item" @click="renameSession(session.session_id)">重命名对话</button>
                            <button class="session-menu-item" @click="exportSession(session.session_id, 'markdown')">导出 Markdown</button>
                            <button class="session-menu-item" @click="exportSession(session.session_id, 'json')">导出 JSON</button>
                            <button class="session-menu-item danger" @click="deleteSession(session.session_id)">删除对话</button>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </template>
              </div>
            </div>
          </div>
          

        </div>
        
        <!-- 右侧显示区域 -->
        <div class="main-container">
          <!-- 用户头像 - 固定在右上角 -->
          <div class="user-avatar-container-fixed" ref="avatarContainerRef">
            <!-- 头像，点击时切换用户信息显示状态 -->
            <img
              :src="userAvatar"
              class="user-avatar"
              alt="用户头像"
              @click="toggleUserInfo"
              tabindex="0"
            />

            <!-- 用户信息下拉框，点击头像时显示/隐藏 -->
            <div class="user-info-dropdown" v-show="showUserInfo">
              <template v-if="currentUser">
                <span class="user-name">{{ currentUser }}</span>
                <button class="btn-tertiary upload-avatar-btn" @click="triggerAvatarUpload">
                  <span role="img" class="semi-icon semi-icon-default text-16">
                    <svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" fill="none" viewBox="0 0 24 24">
                      <path fill="currentColor" d="M12 4a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM6 8a6 6 0 1 1 12 0A6 6 0 0 1 6 8zm2 10a3 3 0 0 0-3 3 1 1 0 1 1-2 0 5 5 0 0 1 5-5h8a5 5 0 0 1 5 5 1 1 0 1 1-2 0 3 3 0 0 0-3-3H8z"/>
                    </svg>
                  </span>
                  上传头像
                </button>
                <input
                  type="file"
                  ref="avatarInput"
                  accept="image/*"
                  style="display: none"
                  @change="handleAvatarUpload"
                />
                <button data-testid="setup_logout" class="btn-tertiary" style="width: 100%; justify-content: flex-start;" @click="handleLogout">
                  <span role="img" class="semi-icon semi-icon-default text-16">
                    <svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" fill="none" viewBox="0 0 24 24">
                      <path fill="currentColor" fill-rule="evenodd" d="M14 3H4.5v18H14v-5h2v5a2 2 0 0 1-2 2H4.5a2 2 0 0 1-2-2V3a2 2 0 0 1 2-2H14a2 2 0 0 1 2 2v5h-2zm5.207 4.793a1 1 0 1 0-1.414 1.414L19.586 11H10.5a1 1 0 1 0 0 2h9.086l-1.793 1.793a1 1 0 0 0 1.414 1.414l3.5-3.5a1 1 0 0 0 0-1.414z" clip-rule="evenodd"></path>
                    </svg>
                  </span>
                  退出登录
                </button>
              </template>
              <template v-else>
                <span class="user-name">当前未登录</span>
                <button class="login-button btn-primary" @click="goToLogin">请登录</button>
              </template>
            </div>
          </div>

          <!-- 最终结果显示框 -->
          <div class="result-container" :class="[{ 'processing': isProcessing }, selectedArchitecture === 'langgraph' ? 'arch-langgraph' : 'arch-agents']">
            <!-- 移除顶部用户信息区域 -->
            
            <div v-if="degradeBanner.visible" class="degrade-banner">
              <div class="degrade-banner-title">知识库降级运行中</div>
              <div class="degrade-banner-text">{{ degradeBanner.text }}</div>
              <button class="degrade-banner-close" @click="degradeBanner.visible = false">知道了</button>
            </div>

            <!-- 统一的消息展示区域 -->
            <div class="chat-message-container" ref="processContent">
              <div v-if="chatMessages.length === 0" class="welcome-panel">
                <p class="welcome-tag">GeoAssist Nova · Field Ops Suite</p>
                <h3>面向地学现场的多智能体协同指挥台</h3>
                <p>整合任务拆解、数据归集与风险评估，让外业小队快速进入协作节奏。</p>
                <div class="welcome-metrics">
                  <span>6+ 协作角色</span>
                  <span>24H 响应机制</span>
                  <span>100% 流程可追溯</span>
                </div>
              </div>
              <div v-for="(msg, index) in chatMessages" :key="index" :class="['message-wrapper', msg.type]">
                 <!-- 消息头/角色标识 -->
                 <div class="message-role-label" v-if="msg.type === 'THINKING'" @click="toggleThinking(index)">
                   <div class="thinking-header">
                     <span class="thinking-text">{{ isProcessing && index === chatMessages.length - 1 ? '思考中...' : '思考过程' }}</span>
                     <svg 
                       xmlns="http://www.w3.org/2000/svg" 
                       width="16" 
                       height="16" 
                       viewBox="0 0 24 24" 
                       fill="none" 
                       stroke="currentColor" 
                       stroke-width="2" 
                       stroke-linecap="round" 
                       stroke-linejoin="round"
                       class="thinking-icon"
                       :class="{ 'collapsed': msg.collapsed }"
                     >
                       <polyline points="6 9 12 15 18 9"></polyline>
                     </svg>
                   </div>
                 </div>
                 
                 <!-- 消息内容 -->
                 <div class="message-content" v-show="msg.type !== 'THINKING' || !msg.collapsed">
                   <div class="markdown-body" v-html="renderMarkdown(msg.content)"></div>
                 </div>
              </div>
            </div>
              
              <!-- 用户输入框 - GPT/豆包风格 -->
              <div class="input-container">
                <!-- 模型配置面板 -->
                <div v-if="showModelConfig" class="model-config-panel">
                  <div class="model-config-section">
                    <div class="model-config-label">当前问答模型</div>
                    <input v-model="runtimeModelConfig.chat_model" type="text" placeholder="如 qwen-plus" />
                  </div>
                  <div class="model-config-section">
                    <div class="model-config-label">当前向量模型</div>
                    <input v-model="runtimeModelConfig.embedding_model" type="text" placeholder="如 text-embedding-v3" />
                  </div>
                  <div class="model-config-section full-width">
                    <div class="model-config-label">Base URL (可选)</div>
                    <input v-model="runtimeModelConfig.base_url" type="text" placeholder="OpenAI兼容端点" />
                  </div>
                  <div class="model-config-section full-width">
                    <div class="model-config-label">API Key (可选)</div>
                    <input v-model="runtimeModelConfig.api_key" type="password" placeholder="自定义API密钥" />
                  </div>
                </div>

                <!-- 主输入框区域 -->
                <div class="input-main">
                  <!-- 附件预览区域 -->
                  <div v-if="uploadedFiles.length > 0" class="file-preview-list">
                    <div v-for="(file, index) in uploadedFiles" :key="index" class="file-preview-item">
                      <span class="file-icon">📎</span>
                      <span class="file-name" :title="file.name">{{ file.name }}</span>
                      <button class="file-download" @click="downloadFile(file)" title="下载">⬇</button>
                      <button class="file-remove" @click="removeFile(index)" title="移除">×</button>
                    </div>
                  </div>

                  <div class="input-box">
                    <!-- 文本输入区 - 顶部横跨整个宽度 -->
                    <textarea
                      ref="inputTextarea"
                      v-model="userInput"
                      placeholder="请输入任务，例如：现场采样路线规划、区域地质快报、钻孔记录整理..."
                      @keyup.enter.exact="handleSend($event)"
                      @input="autoResize"
                      :disabled="isProcessing"
                    ></textarea>

                    <!-- 底部控制栏 -->
                    <div class="input-bottom-bar">
                      <!-- 左下角控制区 -->
                      <div class="input-controls-left">
                        <!-- 文件上传按钮 -->
                        <label class="file-upload-btn" :class="{ disabled: isProcessing }">
                          <input type="file" multiple accept=".txt,.md,.pdf,.doc,.docx,.png,.jpg,.jpeg,.gif" @change="handleFileUpload" :disabled="isProcessing" />
                          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48"></path>
                          </svg>
                        </label>

                        <!-- 架构选择器 - 下拉菜单 -->
                        <div class="arch-selector" ref="archSelectorRef">
                          <button class="arch-trigger" @click="toggleArchMenu">
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                              <polygon points="12 2 2 7 12 12 22 7 12 2"></polygon>
                              <polyline points="2 17 12 22 22 17"></polyline>
                              <polyline points="2 12 12 17 22 12"></polyline>
                            </svg>
                            <span>{{ selectedArchitecture === 'agents' ? 'OpenAI' : 'Graph' }}</span>
                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                              <polyline points="6 9 12 15 18 9"></polyline>
                            </svg>
                          </button>
                          <div v-if="showArchMenu" class="arch-dropdown">
                            <div class="arch-option" :class="{ active: selectedArchitecture === 'agents' }" @click="switchArchitecture('agents'); showArchMenu = false">
                              <div class="arch-option-icon agents-icon">O</div>
                              <div class="arch-option-info">
                                <div class="arch-option-name">OpenAI Agent</div>
                                <div class="arch-option-desc">智能编排 · 轻量高效</div>
                              </div>
                              <div v-if="selectedArchitecture === 'agents'" class="arch-option-check">✓</div>
                            </div>
                            <div class="arch-option" :class="{ active: selectedArchitecture === 'langgraph' }" @click="switchArchitecture('langgraph'); showArchMenu = false">
                              <div class="arch-option-icon langgraph-icon">G</div>
                              <div class="arch-option-info">
                                <div class="arch-option-name">LangGraph</div>
                                <div class="arch-option-desc">状态图谱 · 精细控制</div>
                              </div>
                              <div v-if="selectedArchitecture === 'langgraph'" class="arch-option-check">✓</div>
                            </div>
                          </div>
                        </div>

                        <!-- 记忆模式选择器 - 下拉菜单 -->
                        <div class="memory-selector" ref="memorySelectorRef">
                          <button class="memory-trigger" @click="toggleMemoryMenu">
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                            </svg>
                            <span>{{ selectedMemoryMode === 'file' ? '本地' : 'mem0' }}</span>
                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                              <polyline points="6 9 12 15 18 9"></polyline>
                            </svg>
                          </button>
                          <div v-if="showMemoryMenu" class="memory-dropdown">
                            <div class="memory-option" :class="{ active: selectedMemoryMode === 'file' }" @click="switchMemoryMode('file'); showMemoryMenu = false">
                              <div class="memory-option-icon file-icon">F</div>
                              <div class="memory-option-info">
                                <div class="memory-option-name">本地记忆</div>
                                <div class="memory-option-desc">JSON 文件 · 会话内短期记忆</div>
                              </div>
                              <div v-if="selectedMemoryMode === 'file'" class="memory-option-check">✓</div>
                            </div>
                            <div
                              class="memory-option"
                              :class="{ active: selectedMemoryMode === 'mem0', disabled: !mem0Available }"
                              @click="mem0Available ? (switchMemoryMode('mem0'), showMemoryMenu = false) : null"
                            >
                              <div class="memory-option-icon mem0-icon">M</div>
                              <div class="memory-option-info">
                                <div class="memory-option-name">AI 记忆 (mem0)</div>
                                <div class="memory-option-desc" v-if="mem0Available">向量存储 · 跨会话长期+语义记忆</div>
                                <div class="memory-option-desc error" v-else>{{ mem0StatusMessage }}</div>
                              </div>
                              <div v-if="selectedMemoryMode === 'mem0' && mem0Available" class="memory-option-check">✓</div>
                            </div>
                          </div>
                        </div>

                        <!-- 记忆管理按钮 + 范围选择 -->
                        <div class="memory-mgmt-wrapper" ref="memoryMgmtRef">
                          <button class="memory-mgmt-btn" @click.stop="toggleScopeMenu" title="切换记忆范围">
                            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                              <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
                              <path d="M2 17l10 5 10-5"></path>
                              <path d="M2 12l10 5 10-5"></path>
                            </svg>
                            <span>记忆</span>
                            <span v-if="memoryCount > 0" class="memory-badge">{{ memoryCount }}</span>
                            <span :class="['scope-indicator', memoryScope]">
                              {{ memoryScope === 'global' ? '全局' : '会话' }}
                            </span>
                            <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="scope-chevron">
                              <polyline points="6 9 12 15 18 9"></polyline>
                            </svg>
                          </button>
                          <!-- 记忆范围切换下拉 -->
                          <div v-if="showScopeMenu" class="scope-dropdown">
                            <div class="scope-section-title">记忆范围</div>
                            <div
                              :class="['scope-option', { active: memoryScope === 'global' }]"
                              @click="switchMemoryScope('global'); showScopeMenu = false"
                            >
                              <span class="scope-icon">🧠</span>
                              <span class="scope-name">全局记忆</span>
                              <span class="scope-desc">跨会话共享</span>
                              <span v-if="memoryScope === 'global'" class="scope-check">✓</span>
                            </div>
                            <div
                              :class="['scope-option', { active: memoryScope === 'session' }]"
                              @click="switchMemoryScope('session'); showScopeMenu = false"
                            >
                              <span class="scope-icon">🔒</span>
                              <span class="scope-name">会话记忆</span>
                              <span class="scope-desc">仅当前会话</span>
                              <span v-if="memoryScope === 'session'" class="scope-check">✓</span>
                            </div>
                            <div class="scope-divider"></div>
                            <div class="scope-option view-memories" @click="openMemoryPanel(); showScopeMenu = false">
                              <span class="scope-icon">📋</span>
                              <span class="scope-name">查看/管理记忆</span>
                            </div>
                          </div>
                        </div>

                        <!-- 模型选择器 -->
                        <button class="model-trigger" @click="showModelConfig = !showModelConfig">
                          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="3"></circle>
                            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
                          </svg>
                          <span>{{ runtimeModelConfig.chat_model || '默认模型' }}</span>
                        </button>
                      </div>

                      <!-- 右下角发送按钮 -->
                      <button
                        class="send-btn"
                        :class="{ 'processing': isProcessing, disabled: (!userInput.trim() && uploadedFiles.length === 0 && !isProcessing) }"
                        :disabled="!userInput.trim() && uploadedFiles.length === 0 && !isProcessing"
                        @click="isProcessing ? handleCancel() : handleSend()"
                      >
                        <svg v-if="!isProcessing" xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <line x1="22" y1="2" x2="11" y2="13"></line>
                          <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
                        </svg>
                        <span v-if="!isProcessing" class="send-btn-text">发送</span>
                        <svg v-else xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                          <rect x="6" y="6" width="12" height="12" rx="2"></rect>
                        </svg>
                      </button>
                    </div>
                  </div>

                </div>
              </div>
          </div>
        </div>
      </div>
      </template>
  </div>

  <!-- 记忆管理面板 - 覆盖层 -->
  <div v-if="showMemoryPanel" class="memory-panel-overlay" @click.self="closeMemoryPanel">
    <div class="memory-panel">
      <!-- 面板头部 -->
      <div class="memory-panel-header">
        <div class="memory-panel-title">
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
            <path d="M2 17l10 5 10-5"></path>
            <path d="M2 12l10 5 10-5"></path>
          </svg>
          AI 记忆管理
          <span v-if="userMemories.length > 0" class="memory-count-badge">{{ userMemories.length }}</span>
        </div>
        <div class="memory-scope-toggle">
          <button
            :class="['scope-btn', { active: memoryScope === 'global' }]"
            @click="switchMemoryScope('global')"
            title="全局记忆：跨会话共享"
          >
            🧠 全局记忆
          </button>
          <button
            :class="['scope-btn', { active: memoryScope === 'session' }]"
            @click="switchMemoryScope('session')"
            title="会话记忆：仅当前会话"
          >
            🔒 会话记忆
          </button>
        </div>
        <div class="memory-panel-actions">
          <button class="memory-action-btn cleanup-btn" @click="handleCleanupExpired" :disabled="isLoadingMemories" title="清理90天前的过期记忆">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="23 4 6 8.5 12 17.5"></polyline>
              <path d="M16 4c0 2-2 4-4 4s-4-2-4-4"></path>
            </svg>
            清理过期
          </button>
          <button class="memory-action-btn danger-btn" @click="handleDeleteAll" :disabled="isLoadingMemories || userMemories.length === 0" title="清空所有记忆">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
            清空全部
          </button>
          <button class="memory-close-btn" @click="closeMemoryPanel" title="关闭面板">
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>
      </div>

      <!-- 面板内容 -->
      <div class="memory-panel-body">
        <!-- 加载中 -->
        <div v-if="isLoadingMemories" class="memory-loading">
          <div class="loading-spinner"></div>
          <span>加载中...</span>
        </div>

        <!-- 空状态 -->
        <div v-else-if="userMemories.length === 0 && !isRefiningMemories" class="memory-empty">
          <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" opacity="0.3">
            <path d="M12 2L2 7l10 5 10-5-10-5z"></path>
            <path d="M2 17l10 5 10-5"></path>
            <path d="M2 12l10 5 10-5"></path>
          </svg>
          <p>暂无记忆记录</p>
          <span>在使用 AI 记忆模式对话时，系统会自动记住重要信息</span>
        </div>

        <!-- 记忆/消息列表 -->
        <div v-else class="memory-list">
          <!-- 精炼中提示 -->
          <div v-if="isRefiningMemories" class="memory-refining-banner">
            <div class="refining-spinner"></div>
            <span>正在精炼压缩记忆，请稍候...</span>
          </div>

          <div v-for="mem in userMemories" :key="mem.id" class="memory-card">
            <!-- 显示模式 -->
            <template v-if="editingMemoryId !== mem.id">
              <div class="memory-card-content">
                <div class="memory-header">
                  <!-- 会话消息显示角色标签 -->
                  <template v-if="mem.role">
                    <span class="memory-role-badge" :class="mem.role">
                      {{ mem.role === 'user' ? '💬 对话精炼' : mem.role === 'system' ? '⚙️ 系统' : '🤖 助手' }}
                    </span>
                  </template>
                  <!-- 全局记忆：显示对话精炼标签 -->
                  <template v-else>
                    <span class="memory-role-badge conversation">
                      💬 对话精炼
                    </span>
                  </template>
                </div>
                <p class="memory-text">{{ formatConversationMemory(mem) }}</p>
                <div v-if="!mem.role" class="memory-meta">
                  <span class="memory-time">{{ formatMemoryTime(mem.created_at) }}</span>
                  <!-- 记忆权重可视化 -->
                  <template v-if="mem.importance_score !== undefined">
                    <span class="memory-weight">
                      <span class="weight-bar" :style="{ width: (mem.importance_score * 100) + '%', background: getWeightColor(mem.importance_score) }"></span>
                      {{ mem.freshness_label }}
                    </span>
                    <span class="memory-score" :title="'重要度: ' + mem.importance_score">
                      ★ {{ (mem.importance_score * 5).toFixed(1) }}
                    </span>
                  </template>
                </div>
              </div>
              <div class="memory-card-actions">
                <button class="memory-action-icon delete-icon" @click="handleDeleteMemory(mem)" title="删除">
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6"></polyline>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                  </svg>
                </button>
              </div>
            </template>

            <!-- 编辑模式（仅全局记忆支持） -->
            <template v-else>
              <div class="memory-card-content memory-editing">
                <textarea
                  v-model="editingMemoryText"
                  class="memory-edit-input"
                  rows="3"
                  @keydown.esc="cancelEditMemory"
                ></textarea>
              </div>
              <div class="memory-card-actions">
                <button class="memory-action-btn save-btn" @click="saveEditMemory(mem.id)" title="保存">
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12"></polyline>
                  </svg>
                  保存
                </button>
                <button class="memory-action-btn cancel-btn" @click="cancelEditMemory" title="取消">
                  <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                  </svg>
                  取消
                </button>
              </div>
            </template>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, watch, nextTick, onUnmounted } from 'vue';
import { marked } from 'marked';

// Configure marked options
marked.setOptions({
  breaks: true, // Enable line breaks
  gfm: true,    // Enable GitHub Flavored Markdown
});

// 使用marked库进行markdown渲染
const renderMarkdown = (text) => {
  if (!text) return '';
  try {
    return marked.parse(text);
  } catch (e) {
    console.error('Markdown parsing error:', e);
    return text;
  }
};

export default {
  name: 'App',
  setup() {
    // 登录相关状态
    const isLoggedIn = ref(false); // 默认未登录，需要后端验证
    // 侧边栏展开/收起状态
    const isSidebarExpanded = ref(true);
    const username = ref('');
    const password = ref('');
    const currentUser = ref('');
    const loginError = ref('');
    // 注册相关状态
    const showRegister = ref(false);
    const regUsername = ref('');
    const regDisplayName = ref('');
    const regPassword = ref('');
    const regPasswordConfirm = ref('');
    const registerError = ref('');
    const registerSuccess = ref('');
    // 用户信息显示状态（用于头像点击显示用户信息）
    const showUserInfo = ref(false);
    // 头像和下拉框的引用
    const avatarContainerRef = ref(null);
    const avatarInput = ref(null);

    // 用户头像（从 localStorage 加载或使用默认头像）
    const defaultAvatar = 'https://p3-flow-imagex-sign.byteimg.com/user-avatar/assets/e7b19241fb224cea967dfaea35448102_1080_1080.png~tplv-a9rns2rl98-icon-tiny.png?rcl=202511070904143F9B891FA2E40D7123F0&rk3s=8e244e95&rrcfp=76e58463&x-expires=1765155855&x-signature=nqQBx1W9ABfrm%2FRKkEYZUzsYjE0%3D';
    const userAvatar = ref(localStorage.getItem('userAvatar') || defaultAvatar);

    // 文件上传相关
    const uploadedFiles = ref([]);

    const handleFileUpload = (event) => {
      const files = Array.from(event.target.files || []);
      if (files.length === 0) return;

      files.forEach(file => {
        if (!uploadedFiles.value.some(f => f.name === file.name && f.size === file.size)) {
          uploadedFiles.value.push({
            name: file.name,
            size: file.size,
            type: file.type,
            file: file
          });
        }
      });
      event.target.value = '';
    };

    const removeFile = (index) => {
      uploadedFiles.value.splice(index, 1);
    };

    const downloadFile = (fileInfo) => {
      const blob = new Blob([fileInfo.file], { type: fileInfo.type || 'application/octet-stream' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = fileInfo.name;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    };

    // 架构选择菜单
    const showArchMenu = ref(false);
    const archMenuPosition = ref('up'); // 'up' or 'down'
    const archSelectorRef = ref(null);
    const inputTextarea = ref(null);

    const toggleArchMenu = () => {
      if (showArchMenu.value) {
        showArchMenu.value = false;
      } else {
        // 默认向上展开
        archMenuPosition.value = 'up';
        showArchMenu.value = true;
      }
    };

    // 记忆模式选择菜单
    const showMemoryMenu = ref(false);
    const selectedMemoryMode = ref('file'); // 'file' | 'mem0'
    const memorySelectorRef = ref(null);
    const mem0Available = ref(false);
    const mem0StatusMessage = ref('正在检查...');

    const toggleMemoryMenu = () => {
      showMemoryMenu.value = !showMemoryMenu.value;
    };

    const switchMemoryMode = (mode) => {
      selectedMemoryMode.value = mode;
      localStorage.setItem('memoryMode', mode);
    };

    // 检查 mem0 可用性
    const checkMemoryStatus = async () => {
      try {
        const response = await fetch('http://127.0.0.1:8000/api/memory_status');
        if (response.ok) {
          const data = await response.json();
          if (data.success && data.mem0) {
            mem0Available.value = data.mem0.available;
            mem0StatusMessage.value = data.mem0.message;
            console.log('[记忆状态] mem0 available:', mem0Available.value, 'message:', mem0StatusMessage.value);
          }
        }
      } catch (e) {
        mem0StatusMessage.value = '无法连接后端服务';
        console.error('Memory status check failed:', e);
      }
    };

    // =========================================================================
    // 记忆管理面板
    // =========================================================================
    const showMemoryPanel = ref(false);
    const userMemories = ref([]);
    const isLoadingMemories = ref(false);
    const isRefiningMemories = ref(false);
    let memoryRefreshTimer = null;
    const memoryCount = ref(0);
    const memoryScope = ref('global'); // 'global' | 'session'
    const editingMemoryId = ref(null);
    const editingMemoryText = ref('');

    // 记忆范围切换菜单
    const showScopeMenu = ref(false);
    const memoryMgmtRef = ref(null);

    const toggleScopeMenu = () => {
      showScopeMenu.value = !showScopeMenu.value;
    };

    const openMemoryPanel = async () => {
      showMemoryPanel.value = true;
      await fetchUserMemories();
    };

    const closeMemoryPanel = () => {
      showMemoryPanel.value = false;
      cancelEditMemory();
    };

    const fetchUserMemories = async (skipRefiningCheck = false) => {
      if (!currentUser.value) return;
      isLoadingMemories.value = true;
      const controller = new AbortController();
      const timer = window.setTimeout(() => controller.abort(), 10000);
      try {
        if (memoryScope.value === 'session') {
          // 会话模式：直接从会话文件获取消息
          const currentSid = selectedSessionId.value || 'default_session';
          console.log('[记忆面板] 会话模式, 获取当前会话消息, session:', currentSid);
          const response = await fetch('http://127.0.0.1:8000/api/session_messages', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: currentUser.value, session_id: currentSid }),
            signal: controller.signal
          });
          if (response.ok) {
            const data = await response.json();
            console.log('[记忆面板] 会话消息数:', data.total);
            userMemories.value = (data.messages || []).map((m, idx) => ({
              id: `msg_${idx}`,
              memory: m.content,
              role: m.role,
              message_index: idx,
              session_id: currentSid,
              created_at: Date.now() / 1000,
            }));
            memoryCount.value = userMemories.value.length;
          }
        } else {
          // 全局模式：从 mem0 获取长期记忆
          const body = { user_id: currentUser.value, top_k: 200 };
          console.log('[记忆面板] 全局模式, 请求 mem0 记忆列表');
          const response = await fetch('http://127.0.0.1:8000/api/memories/list', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
            signal: controller.signal
          });
          if (response.ok) {
            const data = await response.json();
            console.log('[记忆面板] 全局记忆数:', data.total || 0);
            userMemories.value = (data.memories || []).filter(m => m.scope_label === 'global');
            console.log('[记忆面板] 过滤后全局记忆数:', userMemories.value.length);
            memoryCount.value = userMemories.value.length;

            // 调试：打印每条记忆的原始数据
            console.log('[记忆面板] 记忆详情:', userMemories.value.map(m => ({
              id: m.id,
              memory: (m.memory || '').slice(0, 60),
              fact_source: m.fact_source,
              fact_category: m.fact_category,
              role: getGlobalMemoryRole(m),
            })));

            // 检查后台是否有正在进行的记忆精炼任务
            if (!skipRefiningCheck) {
              await checkRefiningStatus();
            }
          }
        }
      } catch (e) {
        console.error('获取记忆列表失败:', e);
        userMemories.value = [];
        memoryCount.value = 0;
      } finally {
        window.clearTimeout(timer);
        isLoadingMemories.value = false;
      }
    };

    const checkRefiningStatus = async () => {
      // 检查后端是否有正在进行的记忆精炼任务
      try {
        const response = await fetch('http://127.0.0.1:8000/api/memories/refining_status', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: currentUser.value,
            top_k: 1,
            memory_mode: selectedMemoryMode.value,
          }),
        });
        if (response.ok) {
          const data = await response.json();
          isRefiningMemories.value = data.is_refining === true;
          console.log('[记忆面板] 精炼状态:', isRefiningMemories.value ? '正在精炼中' : '空闲');

          // 如果正在精炼，启动定时刷新
          if (isRefiningMemories.value && !memoryRefreshTimer) {
            console.log('[记忆面板] 检测到后台精炼任务，启动自动刷新...');
            memoryRefreshTimer = window.setInterval(async () => {
              try {
                // 先检查精炼状态
                const statusResp = await fetch('http://127.0.0.1:8000/api/memories/refining_status', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({
                    user_id: currentUser.value,
                    top_k: 1,
                    memory_mode: selectedMemoryMode.value,
                  }),
                });
                if (statusResp.ok) {
                  const statusData = await statusResp.json();
                  isRefiningMemories.value = statusData.is_refining === true;
                  if (!statusData.is_refining) {
                    // 精炼完成，停止刷新并重新加载记忆
                    window.clearInterval(memoryRefreshTimer);
                    memoryRefreshTimer = null;
                    console.log('[记忆面板] 精炼完成，停止自动刷新');
                    await fetchUserMemories(true);
                    return;
                  }
                }
                // 还在精炼中，刷新记忆列表
                const listResp = await fetch('http://127.0.0.1:8000/api/memories/list', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ user_id: currentUser.value, top_k: 200 }),
                });
                if (listResp.ok) {
                  const d = await listResp.json();
                  userMemories.value = (d.memories || []).filter(mm => mm.scope_label === 'global');
                  memoryCount.value = userMemories.value.length;
                }
              } catch (refreshErr) {
                console.warn('[记忆面板] 自动刷新失败:', refreshErr);
              }
            }, 5000); // 每5秒刷新一次
          }
        }
      } catch (e) {
        console.warn('[记忆面板] 检查精炼状态失败:', e);
      }
    };

    // 切换记忆范围并刷新
    const switchMemoryScope = async (scope) => {
      memoryScope.value = scope;
      localStorage.setItem('memoryScope', scope);
      // 不自动切换 memory_mode — 尊重用户的选择
      // file 模式下选择全局范围时，file_memory.save_history 会自动提取到 mem0
      await fetchUserMemories();
    };

    const startEditMemory = (mem) => {
      editingMemoryId.value = mem.id;
      editingMemoryText.value = mem.memory;
    };

    const cancelEditMemory = () => {
      editingMemoryId.value = null;
      editingMemoryText.value = '';
    };

    const saveEditMemory = async (memoryId) => {
      if (!editingMemoryText.value.trim()) return;
      try {
        const response = await fetch('http://127.0.0.1:8000/api/memories/update', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: currentUser.value,
            memory_id: memoryId,
            new_text: editingMemoryText.value
          })
        });
        if (response.ok) {
          const data = await response.json();
          if (data.success) {
            // 更新本地列表
            const idx = userMemories.value.findIndex(m => m.id === memoryId);
            if (idx !== -1) {
              userMemories.value[idx].memory = editingMemoryText.value;
            }
            cancelEditMemory();
          } else {
            window.alert('更新失败: ' + (data.error || '未知错误'));
          }
        }
      } catch (e) {
        window.alert('更新失败: ' + e.message);
      }
    };

    const handleDeleteMemory = async (mem) => {
      if (!window.confirm('确认删除这条记录？')) return;
      try {
        if (memoryScope.value === 'session') {
          // 会话模式：从会话文件中删除消息
          const currentSid = selectedSessionId.value || 'default_session';
          const response = await fetch('http://127.0.0.1:8000/api/delete_session_message', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              user_id: currentUser.value,
              session_id: currentSid,
              message_index: mem.message_index
            })
          });
          if (response.ok) {
            const data = await response.json();
            if (data.success) {
              // 刷新列表
              await fetchUserMemories();
            } else {
              window.alert('删除失败: ' + (data.error || '未知错误'));
            }
          }
        } else {
          // 全局模式：从 mem0 删除记忆
          const response = await fetch('http://127.0.0.1:8000/api/memories/delete', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: currentUser.value, memory_id: mem.id })
          });
          if (response.ok) {
            const data = await response.json();
            if (data.success) {
              userMemories.value = userMemories.value.filter(m => m.id !== mem.id);
              memoryCount.value = userMemories.value.length;
            } else {
              window.alert('删除失败: ' + (data.error || '未知错误'));
            }
          }
        }
      } catch (e) {
        window.alert('删除失败: ' + e.message);
      }
    };

    const handleDeleteAll = async () => {
      if (memoryScope.value === 'session') {
        // 会话模式：清空当前会话文件
        const currentSid = selectedSessionId.value || 'default_session';
        const confirmMsg = `确认清空当前会话 "${currentSid}" 的所有对话记录？此操作不可恢复。`;
        if (!window.confirm(confirmMsg)) return;
        try {
          const response = await fetch('http://127.0.0.1:8000/api/delete_session', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ user_id: currentUser.value, session_id: currentSid })
          });
          if (response.ok) {
            userMemories.value = [];
            memoryCount.value = 0;
            // 重新创建空会话
            await fetch('http://127.0.0.1:8000/api/create_session', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ user_id: currentUser.value, session_id: currentSid })
            });
          }
        } catch (e) {
          window.alert('清空失败: ' + e.message);
        }
      } else {
        // 全局模式：清空 mem0 记忆
        const confirmMsg = '确认清空所有 AI 记忆？此操作不可恢复。';
        if (!window.confirm(confirmMsg)) return;
        try {
          const body = { user_id: currentUser.value };
          const response = await fetch('http://127.0.0.1:8000/api/memories/delete_all', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
          });
          if (response.ok) {
            const data = await response.json();
            if (data.success) {
              userMemories.value = [];
              memoryCount.value = 0;
            } else {
              window.alert('清空失败: ' + (data.error || '未知错误'));
            }
          }
        } catch (e) {
          window.alert('清空失败: ' + e.message);
        }
      }
    };

    const handleCleanupExpired = async () => {
      if (!window.confirm('将清理超过 90 天的记忆，确认继续？')) return;
      try {
        const response = await fetch('http://127.0.0.1:8000/api/memories/cleanup', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: currentUser.value, max_age_days: 90, max_count: 200 })
        });
        if (response.ok) {
          const data = await response.json();
          if (data.success) {
            window.alert(`清理完成：删除 ${data.deleted_count} 条记忆，剩余 ${data.remaining_count} 条`);
            await fetchUserMemories();
          } else {
            window.alert('清理失败: ' + (data.error || '未知错误'));
          }
        }
      } catch (e) {
        window.alert('清理失败: ' + e.message);
      }
    };

    const formatMemoryTime = (timestamp) => {
      if (!timestamp || timestamp === 0) return '最近添加';
      let ts = timestamp;
      // 处理字符串格式的时间戳
      if (typeof timestamp === 'string') {
        ts = parseFloat(timestamp);
        if (isNaN(ts) || ts === 0) return '最近添加';
        // 如果解析后是一个很小的数（如0.0），也认为是无效时间戳
        if (ts < 1000) return '最近添加';
        const d = new Date(timestamp);
        if (isNaN(d.getTime())) return '未知时间';
        ts = d.getTime() / 1000;
      }
      // 如果是毫秒级时间戳（> 10^12），转换为秒
      if (ts > 1e12) ts = ts / 1000;

      const now = Date.now() / 1000;
      const diff = now - ts;
      if (diff < 0) return '刚刚';
      if (diff < 60) return '刚刚';
      if (diff < 3600) return Math.floor(diff / 60) + ' 分钟前';
      if (diff < 86400) return Math.floor(diff / 3600) + ' 小时前';
      if (diff < 2592000) return Math.floor(diff / 86400) + ' 天前';
      if (diff < 31536000) return Math.floor(diff / 2592000) + ' 个月前';
      return Math.floor(diff / 31536000) + ' 年前';
    };

    const getWeightColor = (score) => {
      // score 0-1, 返回对应的颜色
      if (score >= 0.8) return '#34d399'; // 绿色 - 高重要
      if (score >= 0.6) return '#60a5fa'; // 蓝色 - 中高
      if (score >= 0.4) return '#fbbf24'; // 黄色 - 中等
      if (score >= 0.2) return '#fb923c'; // 橙色 - 中低
      return '#94a3b8'; // 灰色 - 低
    };

    // 全局记忆：格式化对话精炼记忆
    const formatConversationMemory = (mem) => {
      if (!mem || !mem.memory) return '';
      let text = mem.memory;

      // 兼容旧格式：移除 [用户]/[助手] 前缀
      if (text.startsWith('[助手]')) text = text.slice(4).trim();
      else if (text.startsWith('[用户]')) text = text.slice(4).trim();

      // 新格式：用户：... | 助手：... → 美化显示
      text = text.replace(/\| 用户：/g, '\n用户：');
      text = text.replace(/\| 助手：/g, '\n助手：');

      return text;
    };

    const getGlobalMemoryRole = (mem) => {
      return 'conversation';
    };

    const getGlobalMemoryRoleIcon = (mem) => {
      return '💬';
    };

    const getGlobalMemoryRoleLabel = (mem) => {
      return '对话精炼';
    };

    // 自动调整textarea高度
    const autoResize = () => {
      if (inputTextarea.value) {
        inputTextarea.value.style.height = 'auto';
        inputTextarea.value.style.height = Math.min(inputTextarea.value.scrollHeight, 200) + 'px';
      }
    };

    // 切换用户信息显示/隐藏
    const toggleUserInfo = () => {
      showUserInfo.value = !showUserInfo.value;
    };

    // 触发头像上传
    const triggerAvatarUpload = () => {
      avatarInput.value?.click();
    };

    // 处理头像上传
    const handleAvatarUpload = (event) => {
      const file = event.target.files?.[0];
      if (!file) return;

      // 检查文件类型
      if (!file.type.startsWith('image/')) {
        alert('请上传图片文件');
        return;
      }

      // 检查文件大小（限制为 2MB）
      if (file.size > 2 * 1024 * 1024) {
        alert('图片大小不能超过 2MB');
        return;
      }

      // 读取文件并转换为 base64
      const reader = new FileReader();
      reader.onload = (e) => {
        const base64 = e.target.result;
        userAvatar.value = base64;
        // 保存到 localStorage
        localStorage.setItem('userAvatar', base64);
        showUserInfo.value = false;
      };
      reader.readAsDataURL(file);
    };

    // 点击外部收起下拉菜单
    const handleClickOutside = (event) => {
      // 关闭用户信息下拉框
      if (showUserInfo.value && avatarContainerRef.value && !avatarContainerRef.value.contains(event.target)) {
        showUserInfo.value = false;
      }

      const menuNode = event.target?.closest?.('.session-menu, .session-menu-trigger');
      if (!menuNode) {
        openedSessionMenuId.value = '';
      }
    };
    
    // 生命周期钩子：组件挂载后添加事件监听器
    onMounted(() => {
      document.addEventListener('click', handleClickOutside);
    });
    
    // 生命周期钩子：组件卸载前移除事件监听器
    onUnmounted(() => {
      document.removeEventListener('click', handleClickOutside);
    });
    
    // 初始化时检查localStorage中的用户信息，恢复currentUser
    const savedUserId = localStorage.getItem('currentUserId');
    if (savedUserId) {
      // 定义测试用户列表，与handleLogin中保持一致
      const validUsers = [
        { username: 'root1', password: '', userId: 'root1' },
        { username: 'root2', password: '', userId: 'root2' },
        { username: 'root3', password: '', userId: 'root3' }
      ];

      // 查找对应的用户并设置currentUser
      const savedUser = validUsers.find(u => u.userId === savedUserId);
      if (savedUser) {
        currentUser.value = savedUser.username;
      }
    }

    // 恢复记忆模式设置
    const savedMemoryMode = localStorage.getItem('memoryMode');
    if (savedMemoryMode && ['file', 'mem0'].includes(savedMemoryMode)) {
      selectedMemoryMode.value = savedMemoryMode;
    }

    // 恢复记忆范围设置
    const savedMemoryScope = localStorage.getItem('memoryScope');
    if (savedMemoryScope && ['global', 'session'].includes(savedMemoryScope)) {
      memoryScope.value = savedMemoryScope;
    }

    console.log('[初始化] memoryMode:', selectedMemoryMode.value, 'memoryScope:', memoryScope.value);

    // 主界面相关状态
    const userInput = ref('');
    const chatMessages = ref([]); // Unified chat history: { type: 'user'|'assistant'|'THINKING'|'PROCESS', content: string }
    const processMessages = ref([]); // Deprecated, kept for safety
    const answerText = ref(''); // Deprecated, kept for safety
    const processContent = ref(null);
    const isProcessing = ref(false); // 标记是否正在处理请求
    let reader = null; // 保存读取器引用，用于取消请求
    
    // 当前选中的导航项
    const selectedNavItem = ref('');
    const selectedArchitecture = ref('agents');
    const degradeBanner = ref({ visible: false, text: '' });
    const showModelConfig = ref(false);
    const runtimeModelConfig = ref({
      provider: 'custom',
      base_url: '',
      api_key: '',
      chat_model: '',
      embedding_model: ''
    });
    const sessionSearchKeyword = ref('');
    const openedSessionMenuId = ref('');
    const sessionMeta = ref({});
    

    // 切换思考过程的折叠状态
    const toggleThinking = (index) => {
      const msg = chatMessages.value[index];
      if (msg && msg.type === 'THINKING') {
        msg.collapsed = !msg.collapsed;
      }
    };
    
    // 暴露给模板
    // return {
    //   toggleThinking,
    //   isLoggedIn,
    //   username,
    //   password,
    //   currentUser,
    

    
    // 处理知识库查询
    const handleKnowledgeBase = async () => {
      console.log('打开知识库查询');
      selectedNavItem.value = 'knowledge';
      selectedSessionId.value = '';
      chatMessages.value = [];
      processMessages.value = [];
      answerText.value = '';

      // 显示知识库查询提示
      chatMessages.value.push({
        type: 'assistant',
        content: '已切换到知识仓智搜模式。在此模式下，所有回答将基于 RAG 知识库内容，不会调用多智能体系统或联网搜索。'
      });
    };

    // 处理服务站查询
    const handleNetworkSearch = () => {
      selectedNavItem.value = 'network';
      selectedSessionId.value = '';
      chatMessages.value = [];
      processMessages.value = [];
      answerText.value = '';

      // 显示待开发提示
      chatMessages.value.push({
        type: 'assistant',
        content: '⚠️ 全网雷达功能正在开发中，敬请期待...'
      });
    };

    const handleServiceStation = () => {
      console.log('打开服务站查询');
      selectedNavItem.value = 'service';
      selectedSessionId.value = '';
      chatMessages.value = [];
      processMessages.value = [];
      answerText.value = '';

      // 显示待开发提示
      chatMessages.value.push({
        type: 'assistant',
        content: '⚠️ 服务枢纽功能正在开发中，敬请期待...'
      });
    };
    
    // 历史会话相关状态
    const sessions = ref([]);
    const selectedSessionId = ref('');
    const isLoadingSessions = ref(false);
    const showSessions = ref(true); // 控制历史会话的显示/隐藏

    const toDateSafe = (v) => {
      const d = new Date(v || '');
      return Number.isNaN(d.getTime()) ? null : d;
    };

    const dayStart = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());

    const filteredSessions = computed(() => {
      const kw = sessionSearchKeyword.value.trim().toLowerCase();
      const sorted = [...sessions.value].sort((a, b) => {
        const ap = sessionMeta.value[a.session_id]?.pinned ? 1 : 0;
        const bp = sessionMeta.value[b.session_id]?.pinned ? 1 : 0;
        if (ap !== bp) return bp - ap;
        return String(b.create_time || '').localeCompare(String(a.create_time || ''));
      });
      if (!kw) return sorted;
      return sorted.filter((s) => {
        const name = sessionDisplayName(s).toLowerCase();
        return name.includes(kw);
      });
    });

    const groupedSessions = computed(() => {
      const now = new Date();
      const todayStart = dayStart(now);
      const yesterdayStart = new Date(todayStart);
      yesterdayStart.setDate(yesterdayStart.getDate() - 1);
      const sevenDaysStart = new Date(todayStart);
      sevenDaysStart.setDate(sevenDaysStart.getDate() - 7);

      const groups = {
        pinned: { key: 'pinned', label: '置顶', items: [] },
        today: { key: 'today', label: '今天', items: [] },
        yesterday: { key: 'yesterday', label: '昨天', items: [] },
        week: { key: 'week', label: '过去7天', items: [] },
        older: { key: 'older', label: '更早', items: [] },
      };

      filteredSessions.value.forEach((s) => {
        if (sessionMeta.value[s.session_id]?.pinned) {
          groups.pinned.items.push(s);
          return;
        }

        const created = toDateSafe(s.create_time);
        if (!created) {
          groups.older.items.push(s);
          return;
        }

        if (created >= todayStart) {
          groups.today.items.push(s);
        } else if (created >= yesterdayStart) {
          groups.yesterday.items.push(s);
        } else if (created >= sevenDaysStart) {
          groups.week.items.push(s);
        } else {
          groups.older.items.push(s);
        }
      });

      return [groups.pinned, groups.today, groups.yesterday, groups.week, groups.older]
        .filter((g) => g.items.length > 0);
    });
    
    // 切换历史会话的显示/隐藏
    const toggleSessions = () => {
      showSessions.value = !showSessions.value;
    };

    // 处理登录
    const handleLogin = async () => {
      loginError.value = '';

      if (!username.value || !password.value) {
        loginError.value = '请输入用户名和密码';
        return;
      }

      try {
        const response = await fetch('http://127.0.0.1:8000/api/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            username: username.value,
            password: password.value,
          }),
        });
        const data = await response.json();

        if (data.success) {
          isLoggedIn.value = true;
          currentUser.value = data.username;
          localStorage.setItem('currentUserId', String(data.user_id));
          localStorage.setItem('currentUserName', data.username);
          localStorage.setItem('currentDisplayName', data.display_name || data.username);
          // 记录登录时间，48小时内免登录
          localStorage.setItem('loginTimestamp', String(Date.now()));
          window.scrollTo(0, 0);
          username.value = '';
          password.value = '';
        } else {
          loginError.value = data.error || '用户名或密码错误';
        }
      } catch (e) {
        loginError.value = `登录请求失败: ${e.message}`;
      }
    };

    // 处理注册
    const handleRegister = async () => {
      registerError.value = '';
      registerSuccess.value = '';

      if (!regUsername.value || regUsername.value.trim().length < 2) {
        registerError.value = '用户名至少2个字符';
        return;
      }
      if (!regPassword.value || regPassword.value.length < 6) {
        registerError.value = '密码至少6个字符';
        return;
      }
      if (regPassword.value !== regPasswordConfirm.value) {
        registerError.value = '两次输入的密码不一致';
        return;
      }

      try {
        const response = await fetch('http://127.0.0.1:8000/api/auth/register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            username: regUsername.value,
            password: regPassword.value,
            display_name: regDisplayName.value,
          }),
        });
        const data = await response.json();

        if (data.success) {
          registerSuccess.value = '注册成功！请返回登录';
          regUsername.value = '';
          regDisplayName.value = '';
          regPassword.value = '';
          regPasswordConfirm.value = '';
        } else {
          registerError.value = data.error || '注册失败';
        }
      } catch (e) {
        registerError.value = `注册请求失败: ${e.message}`;
      }
    };

    // 获取历史会话数据
    const fetchUserSessions = async () => {
      if (!currentUser.value) return;
      
      isLoadingSessions.value = true;
      try {
        const response = await fetch('http://127.0.0.1:8000/api/user_sessions', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({"user_id": currentUser.value})
        });
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        if (data.success && data.sessions) {
          sessions.value = data.sessions;
          // 默认选择最新的会话
          if (data.sessions.length > 0 && !selectedSessionId.value) {
            selectSession(data.sessions[0].session_id);
          }
        }
      } catch (error) {
        console.error('Error fetching sessions:', error);
      } finally {
        isLoadingSessions.value = false;
        // 刷新会话列表后：确保最终结果框滚动到底部
        scrollToBottom();
      }
    };


    
    const getSessionMetaStorageKey = () => `session_meta_${currentUser.value || 'anonymous'}`;

    const loadSessionMeta = () => {
      try {
        const raw = localStorage.getItem(getSessionMetaStorageKey());
        sessionMeta.value = raw ? JSON.parse(raw) : {};
      } catch (e) {
        sessionMeta.value = {};
      }
    };

    const persistSessionMeta = () => {
      localStorage.setItem(getSessionMetaStorageKey(), JSON.stringify(sessionMeta.value));
    };

    const sessionDisplayName = (session) => {
      const sid = session?.session_id;
      const customName = sid ? sessionMeta.value[sid]?.name : '';
      if (customName) return customName;
      return session?.memory?.[0]?.content || '空对话';
    };

    const toggleSessionMenu = (sessionId) => {
      openedSessionMenuId.value = openedSessionMenuId.value === sessionId ? '' : sessionId;
    };

    const togglePinSession = (sessionId) => {
      const oldMeta = sessionMeta.value[sessionId] || {};
      sessionMeta.value = {
        ...sessionMeta.value,
        [sessionId]: {
          ...oldMeta,
          pinned: !oldMeta.pinned,
        },
      };
      persistSessionMeta();
      openedSessionMenuId.value = '';
    };

    const renameSession = (sessionId) => {
      const session = sessions.value.find((s) => s.session_id === sessionId);
      const currentName = sessionDisplayName(session);
      const nextName = window.prompt('请输入新的会话名称', currentName);
      if (nextName === null) return;
      const name = nextName.trim();
      if (!name) return;
      const oldMeta = sessionMeta.value[sessionId] || {};
      sessionMeta.value = {
        ...sessionMeta.value,
        [sessionId]: {
          ...oldMeta,
          name,
        },
      };
      persistSessionMeta();
      openedSessionMenuId.value = '';
    };

    const exportSession = (sessionId, format = 'markdown') => {
      const session = sessions.value.find((s) => s.session_id === sessionId);
      if (!session) return;

      const safeName = (sessionDisplayName(session).slice(0, 30) || 'session').replace(/[\\/:*?"<>|]/g, '_');
      const exportAt = new Date().toLocaleString();

      let content = '';
      let ext = 'txt';
      let mime = 'text/plain;charset=utf-8';

      if (format === 'json') {
        ext = 'json';
        mime = 'application/json;charset=utf-8';
        content = JSON.stringify({
          session_id: sessionId,
          session_name: sessionDisplayName(session),
          exported_at: exportAt,
          messages: session.memory || [],
        }, null, 2);
      } else {
        ext = 'md';
        mime = 'text/markdown;charset=utf-8';
        const lines = [
          `# 对话导出：${sessionDisplayName(session)}`,
          '',
          `- 会话ID：\`${sessionId}\``,
          `- 导出时间：${exportAt}`,
          '',
          '---',
          '',
        ];
        (session.memory || []).forEach((m, idx) => {
          const role = m.role || 'unknown';
          lines.push(`## ${idx + 1}. ${role}`);
          lines.push('');
          lines.push(m.content || '');
          lines.push('');
        });
        content = lines.join('\n');
      }

      const blob = new Blob([content], { type: mime });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${safeName}-${sessionId}.${ext}`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      openedSessionMenuId.value = '';
    };

    // 删除会话
    const deleteSession = async (sessionId) => {
      const userId = localStorage.getItem('currentUserId') || currentUser.value;
      if (!userId || !sessionId) return;

      const ok = window.confirm('确认删除该聊天记录？删除后不可恢复。');
      if (!ok) return;

      try {
        const response = await fetch('http://127.0.0.1:8000/api/delete_session', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ user_id: userId, session_id: sessionId })
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        if (!data.success) {
          throw new Error(data.error || data.message || '删除失败');
        }

        sessions.value = sessions.value.filter(s => s.session_id !== sessionId);

        if (sessionMeta.value[sessionId]) {
          const { [sessionId]: _removed, ...rest } = sessionMeta.value;
          sessionMeta.value = rest;
          persistSessionMeta();
        }

        if (selectedSessionId.value === sessionId) {
          selectedSessionId.value = '';
          chatMessages.value = [];
          processMessages.value = [];
          answerText.value = '';
        }
      } catch (error) {
        console.error('Error deleting session:', error);
        window.alert(`删除失败：${error.message}`);
      }
    };

    // 新建会话
    const createNewSession = async () => {
      // 生成新的会话ID (使用时间戳+随机数确保唯一性)
      const newSessionId = `session_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

      // 创建新会话对象
      const newSession = {
        session_id: newSessionId,
        create_time: new Date().toISOString(),
        memory: [],
        total_messages: 0
      };

      // 将新会话添加到会话列表的最前面
      sessions.value.unshift(newSession);

      // 同步到后端（创建空会话文件，确保刷新后仍存在）
      try {
        await fetch('http://127.0.0.1:8000/api/create_session', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ user_id: currentUser.value, session_id: newSessionId })
        });
      } catch (e) {
        console.warn('新建会话同步到后端失败（不影响使用）:', e);
      }

      // 清空当前内容
      processMessages.value = [];
      answerText.value = '';
      userInput.value = '';

      // 选中新会话
      selectSession(newSessionId);
    };
    
    // 选择会话
    const selectSession = (sessionId) => {
      selectedSessionId.value = sessionId;
      // 清除导航项选中状态
      selectedNavItem.value = '';
      // 找到选中的会话
      const session = sessions.value.find(s => s.session_id === sessionId);
      
      // 清空当前内容
      chatMessages.value = [];
      processMessages.value = [];
      answerText.value = '';
      
      if (session && session.memory && Array.isArray(session.memory) && session.memory.length > 0) {
        let lastType = null;
        
        session.memory.forEach(msg => {
          if (!msg || !msg.content) return;
          
          // 映射角色类型
          let type = msg.role;
          if (type === 'process') type = 'THINKING';
          
          // 合并连续的思考过程
          if (type === 'THINKING' && lastType === 'THINKING') {
            const lastMsg = chatMessages.value[chatMessages.value.length - 1];
            lastMsg.content += '\n' + msg.content;
          } else {
            chatMessages.value.push({
              type: type, // 'user', 'assistant', 'THINKING'
              content: msg.content
            });
          }
          lastType = type;
        });
        
        // 滚动到底部
        nextTick(() => {
          scrollToBottom();
        });
      }
    };
    
    // 处理登出
    const handleLogout = () => {
      isLoggedIn.value = false;
      currentUser.value = '';
      localStorage.removeItem('currentUserId');
      localStorage.removeItem('currentUserName');
      localStorage.removeItem('currentDisplayName');
      localStorage.removeItem('loginTimestamp');
      // 清空聊天内容
      processMessages.value = [];
      answerText.value = '';
      userInput.value = '';
      // 清空会话列表
      sessions.value = [];
      selectedSessionId.value = '';
    };
    
    // 跳转到登录页面
    const goToLogin = () => {
      isLoggedIn.value = false;
      currentUser.value = '';
      localStorage.removeItem('currentUserId');
      localStorage.removeItem('currentUserName');
      localStorage.removeItem('currentDisplayName');
      localStorage.removeItem('loginTimestamp');
    };
    
    // 处理发送请求
      const handleSend = async (event) => {
        // 阻止回车键的默认行为（插入换行）
        if (event) {
          event.preventDefault();
        }
        if (!userInput.value.trim()) return;
        
        // 立即强制滚动到页面顶部，防止页面下移
        window.scrollTo(0, 0);
        
        // 检查登录状态，只有点击发送时才检查
        const userId = localStorage.getItem('currentUserId');
        if (!userId) {
          // 如果没有登录凭证，跳转到登录页面
          isLoggedIn.value = false;
          return;
        }
        
        // 设置处理状态
        isProcessing.value = true;
        
        // 自动收起之前的思考过程
        chatMessages.value.forEach(msg => {
          if (msg.type === 'THINKING') {
            msg.collapsed = true;
          }
        });
        
        // 清空中间流程消息，但保留最终结果框中的历史会话内容
        // 注意：请求结束后会保留处理过程中的最后一条消息
        processMessages.value = [];
        
        // 将会话显示逻辑与历史会话保持一致：添加用户消息
        chatMessages.value.push({
          type: 'user',
          content: userInput.value.trim()
        });
        
        // 兼容旧变量（防止其他引用报错）
        const userMessage = `<div class="user-message">${userInput.value.trim()}</div>\n\n`;
        if (selectedSessionId.value && answerText.value) {
          answerText.value += userMessage;
        } else {
          answerText.value = userMessage;
        }
        
        // 确保userId有值，使用currentUser作为备选
        const finalUserId = userId || currentUser.value;
        
        // 请求发起时：添加用户消息后立即滚动到结果框底部
        scrollToBottom();

        // 如果是知识仓智搜模式，直接调用知识库 API
        if (selectedNavItem.value === 'knowledge') {
          try {
            const response = await fetch('http://127.0.0.1:8000/api/knowledge_query', {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json'
              },
              body: JSON.stringify({
                query: userInput.value.trim(),
                context: {
                  user_id: currentUser.value || 'root1',
                  session_id: null
                },
                mode: 'agents'
              })
            });

            if (!response.ok) {
              throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            const answer = data.answer || '知识库未找到相关内容';

            chatMessages.value.push({
              type: 'assistant',
              content: answer
            });

            scrollToBottom();
          } catch (error) {
            const errorMsg = `知识库查询失败: ${error.message}`;
            chatMessages.value.push({
              type: 'assistant',
              content: errorMsg
            });
            console.error('Error:', error);
          } finally {
            isProcessing.value = false;
            userInput.value = '';
          }
          return;
        }

        // 处理上传的文件内容
        let attachmentsContent = '';
        if (uploadedFiles.value.length > 0) {
          for (const fileInfo of uploadedFiles.value) {
            try {
              const text = await fileInfo.file.text();
              attachmentsContent += `\n\n【附件: ${fileInfo.name}】\n${text}\n`;
            } catch (e) {
              console.error('读取文件失败:', fileInfo.name, e);
            }
          }
        }

        // 清空上传的文件
        uploadedFiles.value = [];

        // 准备请求数据，包含用户ID、选中的会话ID和上传的文件内容
        const requestData = {
          query: userInput.value.trim() + attachmentsContent,
          context: {
            user_id: finalUserId,
            session_id: selectedSessionId.value || ''
          },
          mode: selectedArchitecture.value,
          memory_mode: selectedMemoryMode.value,
          memory_scope: memoryScope.value,
          model_config: runtimeModelConfig.value?.base_url && runtimeModelConfig.value?.api_key && runtimeModelConfig.value?.chat_model
            ? {
                provider: runtimeModelConfig.value.provider || 'custom',
                base_url: runtimeModelConfig.value.base_url,
                api_key: runtimeModelConfig.value.api_key,
                model: runtimeModelConfig.value.chat_model,
              }
            : null,
        };
        

        
        console.log('发送请求，会话ID:', selectedSessionId.value);

        console.log('发送请求，用户ID:', finalUserId);

        console.log('发送请求，memory_mode:', selectedMemoryMode.value, 'memory_scope:', memoryScope.value);
        
        try {
          // 调用后端API
          const response = await fetch('http://127.0.0.1:8000/api/query', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
          });
          
          if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
          }
          
          // 处理流式响应
        reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        
        while (true) {
          const { done, value } = await reader.read();
          
          if (done) {
              // 处理最后一块数据
              if (buffer.trim()) {
                processSSEData(buffer);
                buffer = ''; // 清空缓冲区
              }
              break;
            }
          
          // 解码数据并累积到缓冲区
          const chunk = decoder.decode(value, { stream: true });
          buffer += chunk;
          
          // 按行分割并处理完整的行
          const lines = buffer.split('\n');
          
          // 除了最后一行（可能不完整）外，处理所有行
          for (let i = 0; i < lines.length - 1; i++) {
            const line = lines[i];
            if (line.trim()) {
              processSSEData(line);
            }
          }
          
          // 保留最后一行作为不完整的缓冲区
          buffer = lines[lines.length - 1];
        }
          
        } catch (error) {
          if (!error.name || error.name !== 'AbortError') {
            const errorMsg = `请求失败: ${error.message}`;
            streamTextToProcess(errorMsg + '\n');
            processMessages.value.push({
              type: 'PROCESS',
              text: errorMsg
            });
            console.error('Error:', error);
          }
        } finally {
          isProcessing.value = false;
          reader = null;
          
          // 请求结束时：确保最终结果框滚动到底部
          scrollToBottom();

          // 请求结束后，不自动收起思考过程，保持展开状态以便用户查看
          // const lastMsg = chatMessages.value[chatMessages.value.length - 1];
          // for (let i = chatMessages.value.length - 1; i >= 0; i--) {
          //    if (chatMessages.value[i].type === 'THINKING') {
          //      chatMessages.value[i].collapsed = true;
          //      break; 
          //    }
          // }
          
          // 会话请求结束后：按需刷新会话列表
          // 只在当前会话不在列表中时刷新（新创建的会话），避免每次问答都刷新导致闪烁
          const currentInList = sessions.value.some(s => s.session_id === selectedSessionId.value);
          if (!currentInList) {
            fetchUserSessions();
          }
        }
        
        // 清空输入框
        userInput.value = '';
      };
      
      // 处理SSE格式的数据
    const processSSEData = (data) => {
      try {
        if (typeof data !== 'string') return;

        if (data.startsWith('data:')) {
          const jsonStr = data.substring(5).trim();

          if (jsonStr) {
            try {
              const parsedData = JSON.parse(jsonStr);

              let kind; // 变量名改为 kind
              let text;

              // -----------------------------------------------------------
              // 适配新的 StreamPacket 结构
              // 结构: { content: { kind: "...", text: "...", ... }, ... }
              // -----------------------------------------------------------
              if (parsedData.content && typeof parsedData.content === 'object') {
                // 1. 获取文本内容
                text = parsedData.content.text;

                // 2. 获取内容分类 (kind)
                if (parsedData.content.kind) {
                  // 新版后端字段名为 kind
                  kind = parsedData.content.kind;
                } else if (parsedData.content.type) {
                  // 兼容旧版字段名 type
                  kind = parsedData.content.type;
                }

                // 3. 处理结束信号 (如果内容是 FinishMessageBody)
                if (parsedData.status === 'FINISHED' || parsedData.content.contentType === 'sagegpt/finish') {
                   // 可以在这里处理结束逻辑，目前前端主要靠流结束自动处理
                   return;
                }
              }

              // -----------------------------------------------------------
              // 降级兼容旧逻辑 (防止后端回滚导致前端挂掉)
              // -----------------------------------------------------------
              else if (parsedData.type && parsedData.content) {
                kind = parsedData.type;
                text = parsedData.content;
              }

              // -----------------------------------------------------------
              // 根据 kind 分发处理逻辑
              // -----------------------------------------------------------
              if (kind && text) {
                // console.log('Processing kind:', kind, 'text:', text); // 调试日志

                switch (kind) {
                  case 'ANSWER':
                    stopThinkingAnimation();
                    streamTextToAnswer(text);
                    break;

                  case 'THINKING':
                    streamTextToProcess(text);
                    break;

                  case 'DEGRADE':
                    degradeBanner.value = { visible: true, text };
                    streamTextToProcess(text + '\n');
                    break;

                  case 'PROCESS':
                    streamTextToProcess(text + '\n');
                    // 兼容旧的 processMessages 数组
                    processMessages.value = [...processMessages.value, {
                      type: 'PROCESS',
                      text: text
                    }];
                    scrollToBottom();
                    break;

                  default:
                    console.log('Unknown content kind:', kind);
                    // 默认作为 PROCESS 处理
                    streamTextToProcess(text + '\n');
                }
              }
            } catch (jsonError) {
              console.error('JSON parse error:', jsonError);
            }
          }
        }
      } catch (error) {
        console.error('Error processing SSE data:', error);
      }
    };
      
      // 处理取消请求
      const handleCancel = () => {
        if (reader) {
          reader.cancel();
          reader = null;
        }
        isProcessing.value = false;
        // 取消请求时停止思考动画
        stopThinkingAnimation();
        
        streamTextToProcess('请求已取消\n');
        processMessages.value.push({
          type: 'PROCESS',
          text: '请求已取消'
        });
      };

    // 移除未使用的handleStreamingResponse函数

    // 流式更新答案文本（使用Markdown渲染）
    const streamTextToAnswer = (text) => {
      // 忽略打断思考过程的纯空白字符
      const lastMsg = chatMessages.value[chatMessages.value.length - 1];
      if ((!text || !text.trim()) && lastMsg && lastMsg.type !== 'assistant') {
        return;
      }

      // 处理文本：将多个空格替换为单个空格，多个换行替换为单个换行
      text = text
      // .replace(/[ \t]+/g, ' ')  // 将多个连续空白字符（包括空格、制表符等）替换为单个空格
      .replace(/ +/g, ' ')  // 将多个连续空白字符（包括空格、制表符等）替换为单个空格
      .replace(/\n+/g, '\n'); // 将多个连续换行符替换为单个换行符
      
      // 更新统一的聊天记录
      // const lastMsg = chatMessages.value[chatMessages.value.length - 1]; // 已在函数开头声明
      if (lastMsg && lastMsg.type === 'assistant') {
        lastMsg.content += text;
      } else {
        chatMessages.value.push({ type: 'assistant', content: text });
      }
      chatMessages.value = [...chatMessages.value]; // Trigger reactivity
      
      // 兼容旧变量
      answerText.value += text;
      
      // 后端返回数据时：确保最终结果框滚动到底部
      scrollToBottom();
    };
    
    // 流式更新处理消息
    const streamTextToProcess = (text) => {
      // 更新统一的聊天记录
      const lastMsg = chatMessages.value[chatMessages.value.length - 1];
      if (lastMsg && lastMsg.type === 'THINKING') {
        lastMsg.content += text;
        // 如果是新消息且正在处理中，确保展开
        if (isProcessing.value && lastMsg.collapsed === undefined) {
           // 使用 reactive 属性，初始化为 false (展开)
           lastMsg.collapsed = false;
        }
      } else {
        chatMessages.value.push({ 
          type: 'THINKING', 
          content: text,
          collapsed: false // 默认为展开状态
        });
      }
      chatMessages.value = [...chatMessages.value];
      
      // 兼容旧变量
      const lastProcessMsg = processMessages.value[processMessages.value.length - 1];
      if (lastProcessMsg && lastProcessMsg.type === 'THINKING') {
        lastProcessMsg.text += text;
        processMessages.value = [...processMessages.value];
      } else {
        processMessages.value = [...processMessages.value, {
          type: 'THINKING',
          text: text
        }];
      }
      
      scrollToBottom();
    };
    
    // 移除旧的思考动画逻辑，避免覆盖文本内容
    const startThinkingAnimation = () => {
      // 这里的逻辑已移除，由CSS处理动画效果
    };
    
    // 停止思考动画
    const stopThinkingAnimation = () => {
      // 这里的逻辑已移除
    };
    
    // 保留上面的processSSEData函数实现
      
      // 处理响应数据（兼容旧格式）
      const handleResponseData = (data) => {
        if (data.type === 'ANSWER') {
          // 收到答案时停止思考动画
          stopThinkingAnimation();
          streamTextToAnswer(data.content);
        } else if (data.type === 'THINKING') {
          // THINKING内容使用streamTextToProcess函数处理
          streamTextToProcess(data.content);
        } else if (data.type === 'PROCESS') {
          // 收到其他处理消息时停止思考动画
          stopThinkingAnimation();
          processMessages.value.push({ type: 'PROCESS', text: data.content });
          scrollToBottom();
        }
      };

    // 滚动到底部
    const scrollToBottom = () => {
      setTimeout(() => {
        // 滚动新的消息容器
        const chatContainer = document.querySelector('.chat-message-container');
        if (chatContainer) {
          chatContainer.scrollTop = chatContainer.scrollHeight;
        }
        
        // 确保页面不整体滚动，无条件强制滚动到顶部
        window.scrollTo(0, 0);
      }, 0);
    };

    // 监听登录状态变化，登录成功后获取会话列表
    watch(isLoggedIn, (newVal) => {
      if (newVal && currentUser.value) {
        loadSessionMeta();
        fetchUserSessions();
      }
    });
    
    // 组件挂载时检查登录状态并获取会话列表
    onMounted(() => {
      // 初始化默认管理员账号
      fetch('http://127.0.0.1:8000/api/auth/init_default_user', { method: 'POST' }).catch(() => {});

      // 检查是否有 48 小时内的登录记录，自动恢复登录状态
      const savedUserId = localStorage.getItem('currentUserId');
      const savedUserName = localStorage.getItem('currentUserName');
      const loginTimestamp = localStorage.getItem('loginTimestamp');
      if (savedUserId && savedUserName && loginTimestamp) {
        const elapsed = Date.now() - Number(loginTimestamp);
        const fortyEightHours = 48 * 60 * 60 * 1000;
        if (elapsed < fortyEightHours) {
          isLoggedIn.value = true;
          currentUser.value = savedUserName;
          localStorage.setItem('currentUserId', savedUserId);
        } else {
          // 超过 48 小时，清除登录信息
          localStorage.removeItem('currentUserId');
          localStorage.removeItem('currentUserName');
          localStorage.removeItem('currentDisplayName');
          localStorage.removeItem('loginTimestamp');
        }
      }

      if (isLoggedIn.value && currentUser.value) {
        loadSessionMeta();
        fetchUserSessions();

        // 组件挂载默认加载时：确保最终结果框滚动到底部
        nextTick(() => {
          scrollToBottom();
        });
      }

      // 获取当前模型配置
      fetchModelConfig();

      // 检查 mem0 记忆可用性
      checkMemoryStatus();

      // 添加键盘快捷键监听器
      document.addEventListener('keydown', handleKeyDown);

      // 点击外部关闭范围菜单
      document.addEventListener('mousedown', (e) => {
        if (showScopeMenu.value && memoryMgmtRef.value && !memoryMgmtRef.value.contains(e.target)) {
          showScopeMenu.value = false;
        }
      });
    });

    onUnmounted(() => {
      // 移除键盘快捷键监听器
      document.removeEventListener('keydown', handleKeyDown);
      // 清理记忆自动刷新定时器
      if (memoryRefreshTimer) {
        window.clearInterval(memoryRefreshTimer);
        memoryRefreshTimer = null;
      }
    });
    
    // 处理键盘快捷键
    const handleKeyDown = (event) => {
      // Ctrl+K 快捷键新建会话
      if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
        event.preventDefault();
        createNewSession();
      }
    };
    
    const switchArchitecture = (mode) => {
      selectedArchitecture.value = mode;
    };

    const clearModelConfig = () => {
      runtimeModelConfig.value = {
        provider: 'custom',
        base_url: '',
        api_key: '',
        chat_model: '',
        embedding_model: ''
      };
      showModelConfig.value = false;
    };

    // 切换侧边栏展开/收起状态
    const toggleSidebar = () => {
      isSidebarExpanded.value = !isSidebarExpanded.value;
      console.log('侧边栏状态:', isSidebarExpanded.value ? '展开' : '收起');
    };

    // 获取当前模型配置
    const fetchModelConfig = async () => {
      try {
        const response = await fetch('http://127.0.0.1:8000/api/model_config');
        if (response.ok) {
          const data = await response.json();
          if (data.success && data.config) {
            runtimeModelConfig.value.chat_model = data.config.chat_model || '';
            runtimeModelConfig.value.embedding_model = data.config.embedding_model || '';
            // 不覆盖用户自定义的 base_url 和 api_key
            if (!runtimeModelConfig.value.base_url) {
              runtimeModelConfig.value.base_url = data.config.base_url || '';
            }
          }
        }
      } catch (error) {
        console.error('获取模型配置失败:', error);
      }
    };

    return {
      // 登录相关状态
      isLoggedIn,
      username,
      password,
      currentUser,
      loginError,
      showRegister,
      regUsername,
      regDisplayName,
      regPassword,
      regPasswordConfirm,
      registerError,
      registerSuccess,
      showUserInfo,
      toggleUserInfo,
      avatarContainerRef,
      avatarInput,
      userAvatar,
      triggerAvatarUpload,
      handleAvatarUpload,
      handleLogin,
      handleRegister,
      handleLogout,
      goToLogin,
      // 主界面相关
      userInput,
      chatMessages,
      processMessages,
      answerText,
      processContent,
      isProcessing,
      uploadedFiles,
      handleFileUpload,
      removeFile,
      downloadFile,
      inputTextarea,
      autoResize,
      handleSend,
      handleCancel,
      renderMarkdown,
      // 历史会话相关
      sessions,
      selectedSessionId,
      isLoadingSessions,
      showSessions,
      toggleSessions,
      // 记忆管理面板
      showMemoryPanel,
      userMemories,
      isLoadingMemories,
      memoryCount,
      memoryScope,
      showScopeMenu,
      toggleScopeMenu,
      memoryMgmtRef,
      switchMemoryScope,
      editingMemoryId,
      editingMemoryText,
      isRefiningMemories,
      openMemoryPanel,
      closeMemoryPanel,
      fetchUserMemories,
      startEditMemory,
      cancelEditMemory,
      saveEditMemory,
      handleDeleteMemory,
      handleDeleteAll,
      handleCleanupExpired,
      formatMemoryTime,
      getWeightColor,
      getGlobalMemoryRole,
      getGlobalMemoryRoleIcon,
      getGlobalMemoryRoleLabel,
      formatConversationMemory,
      // 导航栏相关
      selectedNavItem,
      selectedArchitecture,
      selectedMemoryMode,
      showMemoryMenu,
      memorySelectorRef,
      toggleMemoryMenu,
      switchMemoryMode,
      mem0Available,
      mem0StatusMessage,
      checkMemoryStatus,
      degradeBanner,
      showModelConfig,
      runtimeModelConfig,
      switchArchitecture,
      clearModelConfig,
      showArchMenu,
      archMenuPosition,
      archSelectorRef,
      toggleArchMenu,
      handleKnowledgeBase,
      handleNetworkSearch,
      handleServiceStation,
      selectSession,
      fetchUserSessions,
      createNewSession,
      deleteSession,
      sessionSearchKeyword,
      filteredSessions,
      groupedSessions,
      openedSessionMenuId,
      toggleSessionMenu,
      togglePinSession,
      renameSession,
      exportSession,
      sessionMeta,
      sessionDisplayName,

      // 侧边栏相关
      isSidebarExpanded,
      toggleSidebar,
      // 思考过程相关
      toggleThinking
    };
  }
};
</script>

<style scoped>
/* 思考过程头部样式 */
.thinking-header {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
  transition: color 0.2s;
}

.thinking-header:hover {
  color: var(--tech-text-main);
}

.thinking-text {
  font-weight: 500;
}

.thinking-icon {
  transition: transform 0.3s ease;
  opacity: 0.7;
}

.thinking-icon.collapsed {
  transform: rotate(-90deg);
}

.app-container {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 5px;
  padding-bottom: 10px; /* 减小下边距 */
  box-sizing: border-box;
  min-height: 100vh;
  overflow: hidden; /* 防止页面整体滚动 */
}

/* 主内容区域布局 */
.main-content {
  display: flex;
  flex: 1;
  gap: 20px;
  overflow: hidden;
}

/* 左侧历史会话列表样式 */
.sessions-sidebar {
  width: 300px;
  background-color: #fff;
  border: 1px solid #ccc;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.sidebar-header {
  padding: 15px;
  border-bottom: 1px solid #eee;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.sidebar-header h3 {
  margin: 0;
  font-size: 18px;
  color: #333;
}

.refresh-button {
  padding: 6px 12px;
  background-color: #2196F3;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  cursor: pointer;
  transition: background-color 0.3s ease;
}

.refresh-button:hover:not(:disabled) {
  background-color: #1976D2;
}

.refresh-button:disabled {
  background-color: #ccc;
  cursor: not-allowed;
}

.sidebar-wrapper,
.sidebar-content,
.sidebar-main {
  min-height: 0;
}

.sidebar-wrapper {
  position: relative;
  transition: width 0.3s ease;
}

.sidebar-content {
  width: 60px;
  transition: width 0.3s ease;
  overflow: hidden;
}

.sidebar-content.expanded {
  width: 280px;
}

/* 收起时只显示按钮 */
.sidebar-content:not(.expanded) .its-logo-flat {
  display: none;
}

.sidebar-content:not(.expanded) .app-branding {
  justify-content: center;
  padding: 20px 0;
}

.toggle-sidebar-btn {
  background: #f3f4f6;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s ease;
  color: #6b7280;
}

.toggle-sidebar-btn:hover {
  background: #e5e7eb;
  color: #0ea5e9;
  transform: scale(1.05);
}

.sidebar-main {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
}

.sessions-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 10px;
}

.sessions-list-header {
  padding: 12px 16px;
  border-bottom: 1px solid #e5e7eb;
}

.sessions-title {
  font-size: 14px;
  font-weight: 600;
  color: #374151;
}

/* 会话分组 */
.session-group {
  margin-bottom: 8px;
}

.session-group-title {
  font-size: 11px;
  font-weight: 600;
  color: #e2e8f0;
  padding: 6px 8px 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* 会话项 */
.session-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
  gap: 6px;
  color: #f0f0f0;
}

.session-item:hover {
  background: rgba(100, 255, 218, 0.05);
}

.session-item.selected {
  background: rgba(100, 255, 218, 0.1);
  border-left: 3px solid #6366f1;
}

.session-info {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.session-preview {
  font-size: 13px;
  color: #f0f0f0;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  flex: 1;
}

.session-menu-trigger {
  padding: 2px 6px;
  border: none;
  background: transparent;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  color: #9ca3af;
  flex-shrink: 0;
  transition: all 0.15s;
}

.session-menu-trigger:hover {
  background: rgba(255, 255, 255, 0.1);
  color: #f0f0f0;
}



/* 登录页面样式 */
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  flex: 1;
  padding: 20px;
}

.login-form {
  background: white;
  border-radius: 12px;
  padding: 40px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
  width: 100%;
  max-width: 400px;
  text-align: center;
}

.login-logo {
  margin: 0 auto 20px;
}

.login-title {
  margin: 0 0 30px;
  font-size: 28px;
  font-weight: 700;
  color: #333;
  background: linear-gradient(90deg, #59D3FF, #F4B740);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.login-input-group {
  margin-bottom: 20px;
  text-align: left;
}

.login-input-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  color: #555;
}

.login-input-group input {
  width: 100%;
  padding: 12px 16px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 16px;
  transition: border-color 0.3s ease;
  box-sizing: border-box;
}

.login-input-group input:focus {
  outline: none;
  border-color: #2196F3;
  box-shadow: 0 0 0 3px rgba(33, 150, 243, 0.1);
}

.login-error {
  color: #f44336;
  margin-bottom: 20px;
  padding: 10px;
  background-color: #ffebee;
  border-radius: 4px;
}

.login-button {
    width: 100%;
    padding: 14px;
    background-color: #2196F3;
    color: white;
    border: none;
    border-radius: 6px;
    font-size: 16px;
    font-weight: 600;
    cursor: pointer;
    transition: background-color 0.3s ease;
  }

  .login-button:hover {
    background-color: #1976D2;
  }

.login-hint {
  margin-top: 20px;
  padding: 15px;
  background-color: #f5f5f5;
  border-radius: 6px;
  font-size: 14px;
  color: #666;
}

.login-hint p {
  margin: 5px 0;
}

.login-toggle {
  margin-top: 16px;
  font-size: 14px;
  color: #666;
}

.login-toggle a {
  color: #2196F3;
  text-decoration: none;
  margin-left: 4px;
  cursor: pointer;
}

.login-toggle a:hover {
  text-decoration: underline;
}

.login-success {
  margin-top: 10px;
  padding: 8px 12px;
  background-color: #e8f5e9;
  border-radius: 6px;
  font-size: 14px;
  color: #2e7d32;
}

/* 注册表单覆盖层 */
.register-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 9999;
}

.register-form {
  background: white;
  border-radius: 12px;
  padding: 40px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
  width: 100%;
  max-width: 420px;
  text-align: center;
}

.register-title {
  font-size: 22px;
  font-weight: 700;
  color: #1a1a2e;
  margin-bottom: 24px;
}

.login-feature-section {
  margin-top: 24px;
  text-align: left;
  padding: 18px;
  background: #f8fafc;
  border-radius: 10px;
  border: 1px solid #e2e8f0;
}

.login-feature-section h2 {
  margin: 0 0 12px;
  font-size: 18px;
  color: #1f2937;
}

.login-feature-section ul {
  margin: 0 0 16px;
  padding-left: 18px;
  color: #4b5563;
  font-size: 14px;
  line-height: 1.6;
}

.login-screenshot-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.screenshot-card {
  background: linear-gradient(135deg, rgba(89, 211, 255, 0.15), rgba(244, 183, 64, 0.2));
  border: 1px dashed rgba(89, 211, 255, 0.5);
  border-radius: 8px;
  min-height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: #1f2937;
  font-weight: 600;
}

/* 用户头像固定在右上角 */
.user-avatar-container-fixed {
  position: fixed;
  top: 20px;
  right: 30px;
  z-index: 1000;
  cursor: pointer;
}

.user-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  object-fit: cover;
  border: 2px solid #e0e0e0;
  transition: all 0.3s ease;
  cursor: pointer;
}

.user-avatar:hover {
  border-color: #0ea5e9;
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(14, 165, 233, 0.3);
}

.user-info-dropdown {
  position: absolute;
  top: 50px;
  right: 0;
  background: white;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
  padding: 12px;
  min-width: 200px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  z-index: 1001;
}

.user-name {
  font-size: 14px;
  font-weight: 600;
  color: #1f2937;
  padding: 8px 12px;
  border-bottom: 1px solid #e5e7eb;
}

.upload-avatar-btn {
  width: 100%;
  justify-content: flex-start;
  padding: 8px 12px;
  border: none;
  background: transparent;
  cursor: pointer;
  border-radius: 6px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #4b5563;
  transition: background-color 0.2s;
}

.upload-avatar-btn:hover {
  background-color: #f3f4f6;
}

/* 用户信息和登出按钮 */
.user-info {
  display: flex;
  align-items: center;
  gap: 15px;
}

.current-user {
  font-size: 14px;
  color: #666;
  font-weight: 500;
  white-space: nowrap;
}

.logout-button {
  padding: 8px 10.67px;
  background-color: #f44336;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  cursor: pointer;
  transition: background-color 0.3s ease;
}

.logout-button:hover {
  background-color: #d32f2f;
}

/* 顶部标题区域 */
.app-header {
  background-color: white;
  border-radius: 8px;
  padding: 10px 15px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
  margin-top: 10px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.top-user-section {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 12px;
  gap: 12px;
  position: relative;
  z-index: 2;
}

.architecture-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  background: #f5f7fb;
  padding: 6px;
  border-radius: 999px;
  border: 1px solid #e3e8f0;
}

.architecture-toggle .toggle-option {
  border: none;
  background: transparent;
  padding: 6px 14px;
  border-radius: 999px;
  font-size: 13px;
  cursor: pointer;
  color: #4b5563;
  transition: background-color 0.2s, color 0.2s;
}

.architecture-toggle .toggle-option.active {
  background: linear-gradient(90deg, #0ea5e9, #2563eb);
  color: #fff;
  font-weight: 600;
}

.result-container.arch-langgraph .architecture-toggle .toggle-option.active {
  background: linear-gradient(90deg, #9333ea, #7c3aed);
}

.degrade-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid rgba(245, 158, 11, 0.5);
  background: rgba(245, 158, 11, 0.12);
  border-radius: 10px;
  margin-bottom: 10px;
}

.degrade-banner-title {
  font-weight: 700;
  color: #fbbf24;
}

.degrade-banner-text {
  flex: 1;
  color: #fde68a;
  font-size: 13px;
}

.degrade-banner-close {
  border: 1px solid rgba(251, 191, 36, 0.4);
  background: rgba(251, 191, 36, 0.15);
  color: #fde68a;
  border-radius: 8px;
  padding: 4px 10px;
  cursor: pointer;
}

.welcome-panel {
  border: 1px solid rgba(56, 189, 248, 0.25);
  background: rgba(15, 23, 42, 0.4);
  border-radius: 14px;
  padding: 18px;
  margin-bottom: 10px;
}

.welcome-tag {
  color: #38bdf8;
  font-weight: 700;
  margin-bottom: 4px;
}

.welcome-panel h3 {
  margin: 0 0 8px;
}

.welcome-panel p {
  margin: 0;
  color: #94a3b8;
}

.welcome-metrics {
  margin-top: 12px;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.welcome-metrics span {
  font-size: 12px;
  color: #cbd5e1;
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 999px;
  padding: 3px 10px;
}

.session-search-wrap {
  padding: 4px 2px 10px;
}

.session-search-input {
  width: 100%;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: rgba(15, 23, 42, 0.35);
  color: #e2e8f0;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 13px;
}

.session-menu-trigger {
  width: 26px;
  height: 26px;
  line-height: 1;
  border-radius: 8px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: rgba(30, 41, 59, 0.5);
  color: #cbd5e1;
  cursor: pointer;
  padding: 0;
  flex-shrink: 0;
}

.session-menu {
  position: absolute;
  right: 0;
  top: 32px;
  min-width: 156px;
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: #1e293b;
  border-radius: 10px;
  padding: 6px;
  z-index: 999;
  box-shadow: 0 10px 24px rgba(2, 6, 23, 0.45);
}

.session-menu-item {
  width: 100%;
  text-align: left;
  background: transparent;
  color: #e2e8f0;
  border: none;
  border-radius: 6px;
  padding: 8px;
  cursor: pointer;
}

.session-menu-item:hover {
  background: rgba(56, 189, 248, 0.14);
}

.session-menu-item.danger:hover {
  background: rgba(239, 68, 68, 0.2);
}

.session-pin-mark {
  font-size: 12px;
  opacity: 0.85;
}

.qa-controls {
  display: flex;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 10px;
}

.qa-control-group {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.qa-control-label {
  font-size: 12px;
  color: #94a3b8;
}

.qa-arch-group {
  align-items: center;
}

.arch-switch {
  display: inline-flex;
  border: 1px solid rgba(148, 163, 184, 0.35);
  border-radius: 10px;
  overflow: hidden;
  background: rgba(15, 23, 42, 0.38);
}

.arch-btn {
  border: none;
  background: transparent;
  color: #cbd5e1;
  min-width: 120px;
  padding: 7px 12px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
}

.arch-btn + .arch-btn {
  border-left: 1px solid rgba(148, 163, 184, 0.28);
}

.arch-btn.active {
  color: #fff;
  background: linear-gradient(90deg, #0ea5e9, #2563eb);
}

.arch-current {
  font-size: 12px;
  color: #60a5fa;
}

.chip-btn {
  border: 1px solid rgba(148, 163, 184, 0.4);
  background: rgba(15, 23, 42, 0.4);
  color: #e2e8f0;
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  cursor: pointer;
}

.chip-btn.active {
  background: linear-gradient(90deg, #0284c7, #2563eb);
  border-color: transparent;
}

.model-config-panel {
  display: grid;
  grid-template-columns: repeat(3, minmax(140px, 1fr));
  gap: 8px;
  margin-bottom: 10px;
}

.model-config-panel input {
  border: 1px solid rgba(148, 163, 184, 0.35);
  background: rgba(15, 23, 42, 0.35);
  color: #e2e8f0;
  border-radius: 8px;
  padding: 8px 10px;
  font-size: 12px;
}

.app-branding {
  display: flex;
  align-items: center;
  gap: 15px;
}

/* 扁平风格Logo */
.its-logo-flat {
  display: flex;
  align-items: center;
  justify-content: center;
}

.its-logo-flat svg {
  filter: drop-shadow(0 2px 3px rgba(0, 0, 0, 0.1));
}

/* 扁平风格标题 */
.its-title {
  margin: 0;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: 1px;
  font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  text-transform: uppercase;
  /* 蓝色渐变效果 */
  background: linear-gradient(90deg, #2196F3, #90CAF9);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  text-fill-color: transparent;
}

.display-container {
  display: flex;
  flex: 1;
  overflow: hidden;
  margin-top: 5px;
  margin-bottom: 5px;
  min-height: 500px; /* 设置最小高度确保有足够空间显示 */
}

.result-container {
  flex: 1;
  padding: 15px;
  display: flex;
  flex-direction: column;
  /* background-color: #f5f5f5; */
  overflow: visible;
  height: auto;
  box-sizing: border-box;
  border-radius: 8px;
  border: 1px solid #fff; /* 添加默认边框 */
}

/* 程序处理中时的渐变闪烁动画 */
.result-container.processing {
  animation: gradient-pulse 1.5s infinite ease-in-out;
}

@keyframes gradient-pulse {
  0% {
    border-color: #fff;
  }
  50% {
    border-color: #2196F3; /* 蓝色边框 */
  }
  100% {
    border-color: #fff;
  }
}


/* 中间流程框样式 */
.process-container {
  width: 100%;
  max-height: 30%; /* 限制最大高度 */
  min-height: 100px;
  margin: 0 0 15px 0; /* 正常的下边距 */
  padding: 10px;
  background-color: #f8f9fa; 
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-sizing: border-box;
}

.process-container h3,
.result-container h3 {
  margin: 0 0 10px 0;
  color: #333;
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: center;
}

/* 确保标题前有小图标提示 */
.process-container h3::before {
  content: '';
  display: inline-block;
  width: 4px;
  height: 16px;
  background-color: #2196F3;
  margin-right: 8px;
  border-radius: 2px;
}

.process-content {
    flex: 1;
    overflow-y: auto;
    padding: 5px;
    background-color: white;
    border-radius: 4px;
    font-size: 13px;
    border: 1px solid #eee;
  }

.result-content {
  flex: 1;
  overflow-y: auto;
  padding: 0 10px 10px 10px; /* 将上边距减小到0 */
  background-color: white;
  border-radius: 4px;
  white-space: pre-wrap;
  text-align: left;
  font-size: 14px;
  margin-top: 0; /* 确保上边距为0 */
}

.message-item {
    margin-bottom: 8px;
    padding: 5px;
    border-radius: 4px;
    text-align: left;
    line-height: 1.5;
    word-wrap: break-word;
    font-size: 16px !important;
  }

  /* 添加markdown样式 */
  .markdown {
    font-size: 16px !important;
    line-height: 1.6 !important;
  }

  .markdown .paragraph {
    margin-bottom: 16px !important;
    font-size: 16px !important;
    line-height: 1.8 !important;
    color: #333 !important;
  }
  
  /* 确保结果内容中的文本样式 */
  .result-content {
    font-size: 16px !important;
  }
  
  /* 确保段落样式 */
  .result-content p {
    font-size: 16px !important;
    line-height: 1.8 !important;
    margin-bottom: 1px !important;
    margin-top: 1px !important;
    color: #333 !important;
    display: inline-block !important;
  }
  
  /* 添加更多样式以确保匹配用户要求的格式 */
  .result-content > div {
    font-size: 16px !important;
    line-height: 1.8 !important;
  }
  
  /* 确保所有文本元素的样式 */
  .result-content * {
    font-size: 16px !important;
    line-height: 1.8 !important;
    color: #333 !important;
  }
  
  /* 使用深度选择器确保样式穿透组件边界 */
  :deep(.result-content) {
    font-size: 16px !important;
  }
  
  :deep(.result-content) * {
    font-size: 16px !important;
    line-height: 1.8 !important;
    color: #333 !important;
  }
  
  /* 确保段落样式 */
  :deep(.result-content p) {
    font-size: 16px !important;
    line-height: 1.8 !important;
    margin-bottom: 1px !important;
    margin-top: 1px !important;
    color: #333 !important;
    display: inline-block !important;
  }

  /* 用户消息样式 - 右对齐、宽度限制（不超过三分之二）、背景色 */
  /* 在结果框中为用户消息添加样式 */
  :deep(.result-content) {
    position: relative;
  }
  
  :deep(.result-content) [v-pre] {
    white-space: pre-wrap;
    word-break: break-word;
  }
  
  /* 使用CSS伪元素和属性选择器处理标记的用户消息 */
  :deep(.result-content) [v-pre] {
    line-height: 1.6;
  }
  
  /* 用户消息样式 - 使用正则匹配[USER]标记的消息 */
  :deep(.result-content) [v-pre] {
    /* 基础样式 */
    font-size: 14px;
  }
  
  /* 为最终结果框中的用户消息和助手消息添加样式 */
  :deep(.result-content) .user-message {
    background-color: #f5f5f5; /* 浅灰色背景 */
    color: #1565c0;
    display: inline-block; /* 使元素宽度适应内容 */
    text-align: left; /* 默认左对齐 */
    margin-left: auto;
    margin-right: 0;
    max-width: 66.6%; /* 不超过容器的三分之二 */
    border-radius: 8px;
    padding: 10px 15px;
    margin-bottom: 8px;
    word-break: break-word;
    line-height: 1.6;
    white-space: pre-wrap;
  }
  
  /* 使用伪元素技巧实现单行右对齐，多行左对齐 */
  :deep(.result-content) .user-message {
    text-align: left;
  }

  /* 让整个消息块右对齐 */
  :deep(.result-content) {
    text-align: left;
  }
  
  /* 确保助手消息仍然左对齐 */
  :deep(.result-content) .assistant-message {
    text-align: left;
    display: block;
  }
  
  :deep(.result-content) .assistant-message {
    background-color: #ffffff; /* 白色背景 */
    color: #333;
    text-align: left;
    margin-left: 0;
    margin-right: auto;
    max-width: 100%;
    padding: 10px 15px;
    margin-bottom: 8px;
    word-break: break-word;
    line-height: 1.6;
  }
  
  /* 保留.message-item.user样式，以备后续可能的其他用途 */
  .message-item.user {
    background-color: #e3f2fd;
    color: #1565c0;
    text-align: right;
    margin-left: auto;
    max-width: 66.6%; /* 不超过容器的三分之二 */
    border-radius: 8px;
    padding: 10px;
  }

  .message-item.THINKING {
    background-color: #f0f7ff;
    color: #0066cc;
    white-space: pre-wrap; /* 保留空格和换行，但长行依然换行 */
    word-break: break-all; /* 确保超长单词能被截断 */
  }

  .message-item.PROCESS {
    background-color: #f0f7ff;
    color: #0066cc;
    /*background-color: #fff9f0;
    color: #cc6600;
    font-weight: bold; */
  }

  /* Markdown 样式 */
  :deep(h1) {
    font-size: 24px;
    margin: 16px 0 8px;
    color: #333;
  }

  :deep(h2) {
    font-size: 20px;
    margin: 14px 0 7px;
    color: #444;
  }

  :deep(h3) {
    font-size: 18px;
    margin: 12px 0 6px;
    color: #555;
  }

  :deep(p) {
    margin: 8px 0;
    line-height: 1.6;
  }

  :deep(ul), :deep(ol) {
    margin: 8px 0;
    padding-left: 24px;
  }

  :deep(li) {
    margin: 4px 0;
  }

  :deep(pre) {
    background-color: #f5f5f5;
    padding: 12px;
    border-radius: 4px;
    overflow-x: auto;
    font-family: 'Courier New', monospace;
  }

  :deep(code) {
    background-color: #f5f5f5;
    padding: 2px 4px;
    border-radius: 3px;
    font-family: 'Courier New', monospace;
  }

  :deep(strong) {
    font-weight: bold;
  }

  :deep(em) {
    font-style: italic;
  }

  :deep(a) {
    color: #2196f3;
    text-decoration: none;
  }

  :deep(a:hover) {
    text-decoration: underline;
  }

.input-container {
  padding: 0;
  margin-top: auto;
}

.textarea-with-button {
  position: relative;
  display: inline-block;
  width: 100%;
  max-width: 50vw;
}

.textarea-with-button textarea {
  width: 100%;
  padding: 12px 48px 12px 12px;
  border: 1px solid #ccc;
  border-radius: 12px;
  resize: none;
  height: 100px;
  font-size: 16px;
  font-family: inherit;
}

.textarea-with-button .send-button {
  position: absolute;
  bottom: 12px;
  right: 12px;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: none;
  background-color: #4CAF50;
  color: white;
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
}

  .textarea-with-button textarea:focus {
    outline: none;
    border-color: #4CAF50;
    box-shadow: 0 0 0 2px rgba(76, 175, 80, 0.2);
  }
  
  /* Send button styles removed from App.vue to use style.css */

  .textarea-with-button textarea:disabled {
    background-color: #f5f5f5;
    cursor: not-allowed;
  }

  .input-container button {
    padding: 12px 24px;
    background-color: #2196F3;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 16px;
    font-weight: 500;
    transition: background-color 0.3s ease;
  }

  .input-container button:hover {
    background-color: #1976D2;
  }

  .input-container button:active {
    background-color: #1565C0;
  }

  .input-container button.cancel-button {
    background-color: #f44336;
    width: 40px;
    padding: 12px;
    font-size: 16px;
    line-height: 1;
  }

  .input-container button.cancel-button:hover {
    background-color: #d32f2f;
  }

/* 美化滚动条 - 默认隐藏，鼠标悬停时显示 */
.process-content::-webkit-scrollbar {
  width: 0;
  position: absolute;
  right: 0;
  transition: width 0.2s ease;
}

.process-content::-webkit-scrollbar-track {
  background: transparent;
  border-radius: 4px;
}

.process-content::-webkit-scrollbar-thumb {
  background: #888;
  border-radius: 4px;
}

.process-content::-webkit-scrollbar-thumb:hover {
  background: #555;
}

/* 鼠标悬停时显示滚动条 */
.process-content:hover::-webkit-scrollbar {
  width: 8px;
}

/* 最终结果框滚动条样式 - 默认隐藏，鼠标悬停时显示 */
.result-content::-webkit-scrollbar {
  width: 0;
  position: absolute;
  right: 0;
  transition: width 0.2s ease;
}

.result-content:hover::-webkit-scrollbar {
  width: 8px;
}

.result-content::-webkit-scrollbar-track {
  background: transparent;
  border-radius: 4px;
}

.result-content::-webkit-scrollbar-thumb {
  background: #888;
  border-radius: 4px;
}

.result-content::-webkit-scrollbar-thumb:hover {
  background: #555;
}

/* 响应式设计 */
@media (max-width: 768px) {
  .app-container {
    padding: 8px;
    gap: 8px;
  }
  
  .display-container {
    flex-direction: column;
    gap: 15px;
  }
  
  .process-container,
  .result-container {
    min-height: 180px;
  }
  
  .input-container textarea {
    height: 80px;
    font-size: 14px;
  }
  
  /* 响应式登录页面 */
  .login-form {
    padding: 30px 20px;
  }
  
  .login-title {
    font-size: 24px;
  }
  
  /* 响应式顶部导航 */
  .app-header {
    flex-direction: column;
    gap: 10px;
    text-align: center;
  }
  
  .user-info {
    justify-content: center;
  }
}

@media (max-width: 480px) {
  .app-container {
    padding: 10px;
    gap: 10px;
  }
  
  .process-container h3,
  .result-container h3 {
    font-size: 16px;
  }
  
  .input-container {
    flex-direction: column;
  }
  
  .input-container button {
    align-self: flex-end;
    padding: 10px 20px;
  }
  
  /* 小屏幕登录页面 */
  .login-form {
    padding: 20px 15px;
  }
  
  .login-logo svg {
    width: 50px;
    height: 50px;
  }
}
.model-down {
     padding-left: 50px;
     margin-top: 10px;
}

/* ==========================================================================
   输入框底部控制栏布局
   ========================================================================== */

.input-bottom-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 4px 4px;
  gap: 6px;
}

.input-controls-left {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: nowrap;
  min-width: 0;
}

/* 架构选择器 - 紧凑显示 */
.arch-selector {
  position: relative;
}

.arch-trigger {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 8px;
  background: #f5f7fb;
  border: 1px solid #e3e8f0;
  border-radius: 6px;
  font-size: 12px;
  color: #4b5563;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
  min-width: 0;
}

.arch-trigger:hover {
  background: #eef1f6;
  border-color: #c5cdd8;
}

.arch-trigger svg:first-child {
  flex-shrink: 0;
}

.arch-trigger span {
  max-width: 60px;
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: 600;
}

.arch-dropdown {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 0;
  z-index: 100;
  background: #fff;
  border: 1px solid #e3e8f0;
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  padding: 6px;
  min-width: 240px;
}

.arch-option {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}

.arch-option:hover {
  background: #f5f7fb;
}

.arch-option.active {
  background: #eef4ff;
}

.arch-option-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 700;
  color: #fff;
  flex-shrink: 0;
}

.agents-icon {
  background: linear-gradient(135deg, #6366f1, #4f46e5);
}

.langgraph-icon {
  background: linear-gradient(135deg, #f59e0b, #d97706);
}

.arch-option-info {
  flex: 1;
  min-width: 0;
}

.arch-option-name {
  font-size: 13px;
  font-weight: 600;
  color: #1f2937;
}

.arch-option-desc {
  font-size: 11px;
  color: #6b7280;
  margin-top: 2px;
}

.arch-option-check {
  color: #6366f1;
  font-size: 16px;
  font-weight: 700;
}

/* 文件上传按钮 */
.file-upload-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 5px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
  color: #6b7280;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
}

.file-upload-btn:hover {
  background: #f5f7fb;
  border-color: #e3e8f0;
  color: #4b5563;
}

.file-upload-btn.disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.file-upload-btn input[type="file"] {
  display: none;
}

/* 模型选择器 */
.model-trigger {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 5px 8px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
  font-size: 12px;
  color: #6b7280;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.model-trigger:hover {
  background: #f5f7fb;
  border-color: #e3e8f0;
  color: #4b5563;
}

.model-trigger svg:first-child {
  flex-shrink: 0;
}

.model-trigger span {
  max-width: 80px;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 发送按钮 */
.send-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 6px 14px;
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  border: none;
  border-radius: 8px;
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
  white-space: nowrap;
}

.send-btn:hover:not(.disabled) {
  background: linear-gradient(135deg, #2563eb, #1d4ed8);
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.3);
}

.send-btn.disabled {
  opacity: 0.4;
  cursor: not-allowed;
  background: #d1d5db;
}

.send-btn.processing {
  background: #ef4444;
}

.send-btn.processing:hover {
  background: #dc2626;
}

.send-btn-text {
  font-size: 12px;
}

/* ==========================================================================
   记忆模式选择器样式 (与架构选择器保持一致的设计风格)
   ========================================================================== */

.memory-selector {
  position: relative;
}

.memory-trigger {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 10px;
  background: #f5f7fb;
  border: 1px solid #e3e8f0;
  border-radius: 8px;
  font-size: 12px;
  color: #4b5563;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.memory-trigger:hover {
  background: #eef1f6;
  border-color: #c5cdd8;
}

.memory-trigger svg:first-child {
  flex-shrink: 0;
}

.memory-trigger span {
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 记忆模式触发器上的范围标签 */
.scope-badge {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.3px;
  white-space: nowrap;
  flex-shrink: 0;
}

.scope-badge.global {
  background: rgba(99, 102, 241, 0.15);
  color: #6366f1;
  border: 1px solid rgba(99, 102, 241, 0.3);
}

.scope-badge.session {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.memory-dropdown {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 0;
  z-index: 100;
  background: #fff;
  border: 1px solid #e3e8f0;
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  padding: 6px;
  min-width: 260px;
}

/* 下拉菜单中的范围切换区域 */
.memory-dropdown-scope {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 10px;
  margin-bottom: 6px;
  background: #f9fafb;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
}

.scope-label {
  font-size: 12px;
  color: #6b7280;
  white-space: nowrap;
}

.scope-pill {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 4px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #fff;
  font-size: 12px;
  color: #6b7280;
  cursor: pointer;
  transition: all 0.2s;
}

.scope-pill:hover {
  border-color: #9ca3af;
  color: #374151;
}

.scope-pill.active {
  font-weight: 600;
  border-color: #6366f1;
  background: #eef2ff;
  color: #4f46e5;
}

.scope-pill.active[style*="session"],
.scope-pill.session.active {
  border-color: #10b981;
  background: #ecfdf5;
  color: #059669;
}

.memory-option {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}

.memory-option:hover {
  background: #f5f7fb;
}

.memory-option.active {
  background: #eef4ff;
}

.memory-option-icon {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 700;
  color: #fff;
  flex-shrink: 0;
}

.file-icon {
  background: linear-gradient(135deg, #6366f1, #4f46e5);
}

.mem0-icon {
  background: linear-gradient(135deg, #10b981, #059669);
}

.memory-option-info {
  flex: 1;
  min-width: 0;
}

.memory-option-name {
  font-size: 13px;
  font-weight: 600;
  color: #1f2937;
}

.memory-option-desc {
  font-size: 11px;
  color: #6b7280;
  margin-top: 2px;
}

.memory-option-desc.error {
  color: #ef4444;
  font-style: italic;
}

.memory-option.disabled {
  opacity: 0.5;
  cursor: not-allowed !important;
  pointer-events: none;
}

.memory-option-check {
  color: #6366f1;
  font-size: 16px;
  font-weight: 700;
}

/* ==========================================================================
   记忆管理面板样式
   ========================================================================== */

/* 记忆管理按钮包装器 */
.memory-mgmt-wrapper {
  position: relative;
}

/* 记忆管理按钮 */
.memory-mgmt-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  background: rgba(56, 189, 248, 0.08);
  border: 1px solid rgba(56, 189, 248, 0.2);
  border-radius: 6px;
  color: var(--tech-text-muted);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.memory-mgmt-btn:hover {
  background: rgba(56, 189, 248, 0.15);
  border-color: rgba(56, 189, 248, 0.4);
  color: var(--tech-text-main);
}

.memory-mgmt-btn svg:first-child {
  flex-shrink: 0;
}

/* 范围指示标签 */
.scope-indicator {
  display: inline-flex;
  align-items: center;
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 10px;
  font-weight: 600;
  white-space: nowrap;
}

.scope-indicator.global {
  background: rgba(99, 102, 241, 0.15);
  color: #6366f1;
}

.scope-indicator.session {
  background: rgba(16, 185, 129, 0.15);
  color: #10b981;
}

/* 范围下拉箭头 */
.scope-chevron {
  flex-shrink: 0;
  opacity: 0.5;
  transition: transform 0.2s;
}

/* 记忆范围下拉菜单 */
.scope-dropdown {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 0;
  z-index: 100;
  background: #fff;
  border: 1px solid #e3e8f0;
  border-radius: 10px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
  padding: 8px;
  min-width: 220px;
}

.scope-section-title {
  font-size: 11px;
  font-weight: 600;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  padding: 4px 8px 8px;
}

.scope-option {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.15s;
}

.scope-option:hover {
  background: #f5f7fb;
}

.scope-option.active {
  background: #eef4ff;
}

.scope-option.view-memories {
  background: rgba(56, 189, 248, 0.08);
  border: 1px dashed rgba(56, 189, 248, 0.3);
}

.scope-option.view-memories:hover {
  background: rgba(56, 189, 248, 0.15);
}

.scope-icon {
  font-size: 16px;
  flex-shrink: 0;
}

.scope-name {
  font-size: 13px;
  font-weight: 600;
  color: #1f2937;
  flex-shrink: 0;
}

.scope-desc {
  font-size: 11px;
  color: #9ca3af;
  margin-left: auto;
}

.scope-check {
  color: #6366f1;
  font-size: 16px;
  font-weight: 700;
  flex-shrink: 0;
}

.scope-divider {
  height: 1px;
  background: #e5e7eb;
  margin: 6px 0;
}

.memory-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  background: #3b82f6;
  color: white;
  font-size: 10px;
  font-weight: 600;
  border-radius: 8px;
}

/* 覆盖层 */
.memory-panel-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: flex-end;
  justify-content: center;
  z-index: 9999;
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

/* 面板主体 */
.memory-panel {
  width: 100%;
  max-width: 600px;
  max-height: 70vh;
  background: #1e293b;
  border-radius: 16px 16px 0 0;
  box-shadow: 0 -8px 32px rgba(0, 0, 0, 0.4);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  animation: slideUp 0.25s ease;
}

@keyframes slideUp {
  from { transform: translateY(100%); }
  to { transform: translateY(0); }
}

/* 面板头部 */
.memory-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  flex-shrink: 0;
}

.memory-panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--tech-text-main);
}

.memory-panel-title svg {
  color: #3b82f6;
}

.memory-count-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  background: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
  font-size: 11px;
  font-weight: 600;
  border-radius: 10px;
}

.memory-scope-toggle {
  display: flex;
  gap: 4px;
  background: rgba(0, 0, 0, 0.2);
  border-radius: 8px;
  padding: 3px;
}

.scope-btn {
  padding: 4px 10px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--tech-text-muted);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.scope-btn:hover {
  color: var(--tech-text-main);
}

.scope-btn.active {
  background: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
}

.memory-panel-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.memory-action-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 6px;
  color: var(--tech-text-muted);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s;
}

.memory-action-btn:hover:not(:disabled) {
  background: rgba(255, 255, 255, 0.1);
  color: var(--tech-text-main);
}

.memory-action-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.memory-action-btn.cleanup-btn {
  border-color: rgba(59, 130, 246, 0.3);
  color: #60a5fa;
}

.memory-action-btn.cleanup-btn:hover:not(:disabled) {
  background: rgba(59, 130, 246, 0.15);
}

.memory-action-btn.danger-btn {
  border-color: rgba(239, 68, 68, 0.3);
  color: #f87171;
}

.memory-action-btn.danger-btn:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.15);
}

.memory-close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: transparent;
  border: none;
  color: var(--tech-text-muted);
  cursor: pointer;
  border-radius: 6px;
  transition: all 0.2s;
  margin-left: 4px;
}

.memory-close-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: var(--tech-text-main);
}

/* 面板内容区 */
.memory-panel-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
}

.memory-panel-body::-webkit-scrollbar {
  width: 6px;
}

.memory-panel-body::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 3px;
}

/* 加载状态 */
.memory-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 0;
  color: var(--tech-text-muted);
  gap: 12px;
}

.loading-spinner {
  width: 24px;
  height: 24px;
  border: 2px solid rgba(255, 255, 255, 0.1);
  border-top-color: #3b82f6;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 精炼中提示 */
.memory-refining-banner {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 14px 20px;
  margin-bottom: 12px;
  background: rgba(59, 130, 246, 0.08);
  border: 1px dashed rgba(59, 130, 246, 0.3);
  border-radius: 10px;
  color: #60a5fa;
  font-size: 14px;
  gap: 10px;
}

.refining-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(96, 165, 250, 0.2);
  border-top-color: #60a5fa;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  flex-shrink: 0;
}

/* 空状态 */
.memory-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 0;
  color: var(--tech-text-muted);
  text-align: center;
  gap: 8px;
}

.memory-empty p {
  font-size: 14px;
  color: var(--tech-text-main);
  margin: 0;
}

.memory-empty span {
  font-size: 12px;
}

/* 记忆列表 */
.memory-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.memory-card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 10px;
  padding: 12px 14px;
  transition: all 0.2s;
  position: relative;
}

.memory-card:hover {
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(255, 255, 255, 0.15);
}

.memory-card-content {
  margin-bottom: 8px;
  padding-right: 70px;
}

.memory-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
}

.memory-scope-badge {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.memory-scope-badge.global {
  background: rgba(99, 102, 241, 0.2);
  color: #818cf8;
  border: 1px solid rgba(99, 102, 241, 0.3);
}

.memory-scope-badge.session {
  background: rgba(16, 185, 129, 0.2);
  color: #34d399;
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.memory-role-badge {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.memory-role-badge.user {
  background: rgba(99, 102, 241, 0.2);
  color: #818cf8;
  border: 1px solid rgba(99, 102, 241, 0.3);
}

.memory-role-badge.assistant {
  background: rgba(16, 185, 129, 0.2);
  color: #34d399;
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.memory-role-badge.system {
  background: rgba(107, 114, 128, 0.2);
  color: #9ca3af;
  border: 1px solid rgba(107, 114, 128, 0.3);
}

.memory-role-badge.conversation {
  background: rgba(139, 92, 246, 0.2);
  color: #a78bfa;
  border: 1px solid rgba(139, 92, 246, 0.3);
}

.memory-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.memory-weight {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--tech-text-muted);
  position: relative;
  flex: 1;
  min-width: 80px;
}

.weight-bar {
  display: inline-block;
  height: 4px;
  min-width: 20px;
  max-width: 60px;
  border-radius: 2px;
  transition: width 0.3s, background 0.3s;
}

.memory-score {
  font-size: 11px;
  color: #fbbf24;
  font-weight: 600;
  white-space: nowrap;
}

.memory-text {
  margin: 0 0 6px 0;
  font-size: 13px;
  line-height: 1.5;
  color: var(--tech-text-main);
  word-break: break-word;
}

.memory-time {
  font-size: 11px;
  color: var(--tech-text-muted);
}

.memory-card-actions {
  position: absolute;
  top: 6px;
  right: 6px;
  display: flex;
  gap: 4px;
  opacity: 0;
  transition: opacity 0.2s;
  z-index: 5;
}

.memory-card:hover .memory-card-actions {
  opacity: 1;
}

.memory-action-icon {
  display: inline-flex !important;
  align-items: center;
  justify-content: center;
  width: 34px !important;
  height: 34px !important;
  padding: 0 !important;
  margin: 0;
  background: rgba(30, 30, 50, 0.9) !important;
  border: 1px solid rgba(255, 255, 255, 0.15) !important;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  color: #c9cdd5 !important;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
  backdrop-filter: none !important;
  font-size: 0 !important;
  font-weight: 400 !important;
  font-family: inherit !important;
  line-height: 1 !important;
}

.memory-action-icon svg {
  display: block;
  width: 16px !important;
  height: 16px !important;
  flex-shrink: 0;
}

.memory-action-icon.edit-icon svg {
  stroke: #c9cdd5 !important;
  fill: none !important;
}

.memory-action-icon.delete-icon svg {
  stroke: #f87171 !important;
  fill: none !important;
}

.memory-action-icon.edit-icon:hover {
  background: rgba(59, 130, 246, 0.3) !important;
  border-color: rgba(59, 130, 246, 0.5) !important;
  transform: scale(1.1);
}

.memory-action-icon.edit-icon:hover svg {
  stroke: #60a5fa !important;
}

.memory-action-icon.delete-icon:hover {
  background: rgba(239, 68, 68, 0.3) !important;
  border-color: rgba(239, 68, 68, 0.5) !important;
  transform: scale(1.1);
}

.memory-action-icon.delete-icon:hover svg {
  stroke: #ff6b6b !important;
}

/* 编辑模式 */
.memory-editing .memory-edit-input {
  width: 100%;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 6px;
  padding: 8px 10px;
  color: var(--tech-text-main);
  font-size: 13px;
  line-height: 1.5;
  resize: vertical;
  font-family: inherit;
}

.memory-editing .memory-edit-input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.2);
}

.memory-card-actions .save-btn {
  border-color: rgba(34, 197, 94, 0.3);
  color: #4ade80;
}

.memory-card-actions .save-btn:hover {
  background: rgba(34, 197, 94, 0.15);
}

.memory-card-actions .cancel-btn {
  border-color: rgba(255, 255, 255, 0.1);
}
</style>
