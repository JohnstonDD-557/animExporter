# World of Warships animation Converter(.anim)

用于导出战舰世界动画文件(.anim)的Blender插件

## 如何安装插件

1. 在[这里](https://github.com/JohnstonDD-557/animExporter/releases)下载插件的安装包(因为有懒狗,所以不一定是最新的)。
2. 启动Blender 在左上角 编辑 -> 偏好设置 -> 插件 -> 安装 然后找到刚刚下载的压缩包,点击安装插件即可使用。

## 插件使用注意事项

1. 骨骼以及其对应顶点组的命名应当为 ```***_BlendBone```
2. 每个顶点仅能包含至多3个顶点组(可以使用Tools中的[权重限3](./Tools/权重限3)强制清理)
3. 同时,可以使用Tools中的[生成轴](./Tools/生成轴)生成骨骼对应的空物体组(导出对应visual文件时需要)

## TODO
