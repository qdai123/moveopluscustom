/** @odoo-module */

import { registry } from "@web/core/registry";
import { CharField } from "@web/views/fields/char/char_field";
const { Component,reactive, onWillUnmount, onWillUpdateProps, useEffect, useRef, useState, onMounted, willStart } = owl;

export class KsGraphPreview extends Component{
    setup(){
    var self =this;
    this.root =null;
    this.graphref = useRef("graph");
    this.kschartref = useRef("kschart");
    useEffect(() => {
        if (this.root){
            this.root.dispose()
        }
        this._Ks_render()
        });

}
      _Ks_render(){
        var self = this;
        var rec = this.props.record.data;
        if ($(self.graphref.el).find("div.graph_text").length){
            $(self.graphref.el).find("div.graph_text").remove();
        }
       if (rec.ks_dashboard_item_type !== 'ks_tile' && rec.ks_dashboard_item_type !== 'ks_kpi' && rec.ks_dashboard_item_type !== 'ks_list_view' && rec.ks_dashboard_item_type !== 'ks_to_do'){
            if(rec.ks_data_calculation_type !== "query"){
                if (rec.ks_model_id) {
                    if (rec.ks_chart_groupby_type == 'date_type' && !rec.ks_chart_date_groupby) {
                        return  $(self.graphref.el).append($("<div class='graph_text'>").text("Select Group by date to create chart based on date groupby"));
                    } else if (rec.ks_dashboard_item_type !== 'ks_scatter_chart' && rec.ks_chart_data_count_type === "count" && !rec.ks_chart_relation_groupby) {
                        $(self.graphref.el).append($("<div class='graph_text'>").text("Select Group By to create chart view"));
                    } else if ( rec.ks_dashboard_item_type !== 'ks_scatter_chart' && rec.ks_chart_data_count_type !== "count" && (rec.ks_chart_measure_field.count === 0 || !rec.ks_chart_relation_groupby)) {
                        $(self.graphref.el).append($("<div class='graph_text'>").text("Select Measure and Group By to create chart view"));
                    } else if (rec.ks_dashboard_item_type !== 'ks_scatter_chart' && !rec.ks_chart_data_count_type) {
                        $(self.graphref.el).append($("<div class='graph_text'>").text("Select Chart Data Count Type"));
                    }else if(rec.ks_dashboard_item_type === "ks_scatter_chart"){
                        if(rec.ks_scatter_measure_x_id && rec.ks_chart_measure_field  ){
                            this.get_chart(rec);
                        }else{
                            $(self.graphref.el).append($("<div class='graph_text'>").text("Please Choose Measures"));
                        }
                }
                     else {
                        this.get_chart(rec);
                    }
                } else {
                    $(self.graphref.el).append($("<div class='graph_text'>").text("Select a Model first."));
                }
            }else if(rec.ks_data_calculation_type === "query" && rec.ks_query_result) {
                if(rec.ks_xlabels && rec.ks_ylabels){
                        this.get_chart(rec);
                } else {
                    $(self.graphref.el).append($("<div class='graph_text'>").text("Please choose the X-labels and Y-labels"));
                }
            }else {
                    $(self.graphref.el).append($("<div class='graph_text'>").text("Please run the appropriate Query"));
            }

        }
    }
    get_chart(rec){
        if($(this.graphref.el).find(".graph_text").length){
            $(this.graphref.el).find(".graph_text").remove();
        }
        const chart_data = JSON.parse(this.props.record.data.ks_chart_data);
        var ks_labels = chart_data['labels'];
        var ks_data = chart_data.datasets;

        let data=[];
        if (ks_data && ks_labels){
        if (ks_data.length && ks_labels.length){
            for (let i=0 ; i<ks_labels.length ; i++){
                let data2={};
                for (let j=0 ;j<ks_data.length ; j++){
                    if (ks_data[j].type == "line"){
                    data2[ks_data[j].label] = ks_data[j].data[i]
                    }else{
                    data2[ks_data[j].label] = ks_data[j].data[i]
                    }
                }
                data2["category"] = ks_labels[i]
                data.push(data2)
            }


            this.root = am5.Root.new(this.graphref.el);
            var self =this;

            const theme = this.props.record.data.ks_chart_item_color
            switch(theme){
            case "default":
                this.root.setThemes([am5themes_Animated.new(this.root)]);
                break;
            case "dark":
                this.root.setThemes([am5themes_Dataviz.new(this.root)]);
                break;
            case "material":
                this.root.setThemes([am5themes_Material.new(this.root)]);
                break;
            case "moonrise":
                this.root.setThemes([am5themes_Moonrise.new(this.root)]);
                break;
            };


            var chart_type = this.props.record.data.ks_dashboard_item_type
            switch (chart_type){
            case "ks_bar_chart":
            var chart = this.root.container.children.push(am5xy.XYChart.new(this.root, {panX: false,panY: false,
             wheelX: "panX",wheelY: "zoomX",layout: this.root.verticalLayout}));

            var xRenderer = am5xy.AxisRendererX.new(this.root, {
                minGridDistance: 15,
                minorGridEnabled: true
            });
            xRenderer.labels.template.setAll({
              direction: "rtl",
              rotation: -45,
              centerY: am5.p50,
              centerX: am5.p100,
              paddingRight: 10
            });

            var xAxis = chart.xAxes.push(am5xy.CategoryAxis.new(this.root, {categoryField: "category",
            renderer: xRenderer,tooltip: am5.Tooltip.new(this.root, {})}));

            xRenderer.grid.template.setAll({location: 1})

            xAxis.data.setAll(data);

            var yAxis = chart.yAxes.push(am5xy.ValueAxis.new(this.root, {extraMin: 0,
            extraMax: 0.1,renderer: am5xy.AxisRendererY.new(this.root, {strokeOpacity: 0.1}) }));

            // Add series

            for (let k = 0;k<ks_data.length ; k++){
                var tooltip = am5.Tooltip.new(this.root, {
                        textAlign: "center",
                        centerX: am5.percent(96),
                        pointerOrientation: "horizontal",
                        labelText: "{categoryX}, {name}: {valueY}"
                    });
                    tooltip.label.setAll({
                        direction: "rtl"
                    })
                if (self.props.record.data.ks_bar_chart_stacked == true && ks_data[k].type != "line"){
                    var series = chart.series.push(am5xy.ColumnSeries.new(self.root, {
                        stacked: true,
                        name: `${ks_data[k].label}`,
                        xAxis: xAxis,
                        yAxis: yAxis,
                        valueYField:`${ks_data[k].label}`,
                        categoryXField: "category",
                        tooltip: tooltip
                    }));
                    series.data.setAll(data);
                }else if (ks_data[k].type != "line"){
                    var series = chart.series.push(am5xy.ColumnSeries.new(self.root, {
                        name: `${ks_data[k].label}`,
                        xAxis: xAxis,
                        yAxis: yAxis,
                        valueYField:`${ks_data[k].label}`,
                        categoryXField: "category",
                        tooltip: tooltip
                    }));
                        series.data.setAll(data);
                }

                if (self.props.record.data.ks_show_records == true && series){
                    series.columns.template.setAll({
                        tooltipY: 0,
                        templateField: "columnSettings"
                   });
                    var cursor = chart.set("cursor", am5xy.XYCursor.new(this.root, {
                            behavior: "zoomY"
                    }));
                   cursor.lineY.set("forceHidden", true);
                   cursor.lineX.set("forceHidden", true);
                }
                if (self.props.record.data.ks_show_data_value == true && series){
                    series.bullets.push(function () {
                        return am5.Bullet.new(self.root, {
//                            locationY:1,
                                sprite: am5.Label.new(self.root, {
                                  text:  "{valueY}",
                                  centerY: am5.p100,
                                  centerX: am5.p50,
                                  populateText: true
                                })
                        });
                    });
                }

                if (self.props.record.data.ks_chart_measure_field_2 && ks_data[k].type == "line"){
                    var tooltip = am5.Tooltip.new(this.root, {
                        textAlign: "center",
                        centerX: am5.percent(96),
                        pointerOrientation: "horizontal",
                        labelText: "{categoryX}, {name}: {valueY}"
                    });
                    tooltip.label.setAll({
                        direction: "rtl"
                    })

                    var series2 = chart.series.push(
                        am5xy.LineSeries.new(self.root, {
                            name: `${ks_data[k].label}`,
                            xAxis: xAxis,
                            yAxis: yAxis,
                            valueYField:`${ks_data[k].label}`,
                            categoryXField: "category",
                            tooltip: tooltip
                        })
                    );

                    series2.strokes.template.setAll({strokeWidth: 3,templateField: "strokeSettings"});
                    series2.data.setAll(data);

                    series2.bullets.push(function() {
                        return am5.Bullet.new(self.root, {
                            sprite: am5.Circle.new(self.root, {
                                strokeWidth: 3,
                                stroke: series2.get("stroke"),
                                radius: 5,
                                fill: self.root.interfaceColors.get("background")
                            })
                        });
                    });
                }
            }
            break;
            case "ks_horizontalBar_chart":
                var chart = this.root.container.children.push(am5xy.XYChart.new(this.root, {panX: false,panY: false,
                wheelX: "panX",wheelY: "zoomX",layout: this.root.verticalLayout}));
                var yRenderer = am5xy.AxisRendererY.new(this.root, {
                        inversed: true,
                        minGridDistance: 30,
                        minorGridEnabled: true,
                        cellStartLocation: 0.1,
                        cellEndLocation: 0.9
                    })
                 yRenderer.labels.template.setAll({
                  direction: "rtl",
                });

                var yAxis = chart.yAxes.push(am5xy.CategoryAxis.new(this.root, {
                    categoryField: "category",
                    renderer: yRenderer
                }))

                yAxis.data.setAll(data);

                var xAxis = chart.xAxes.push(am5xy.ValueAxis.new(this.root, {
                    renderer: am5xy.AxisRendererX.new(this.root, {
                        strokeOpacity: 0.1
                    }),
                    min: 0
                }));
                for (let k = 0;k<ks_data.length ; k++){
                    var tooltip = am5.Tooltip.new(this.root, {
                        textAlign: "center",
                        centerX: am5.percent(96),
                        pointerOrientation: "horizontal",
                        labelText: "{categoryY}, {name}: {valueX}"
                    });

                    tooltip.label.setAll({
                        direction: "rtl"
                    })
                if (self.props.record.data.ks_bar_chart_stacked == true  && ks_data[k].type != "line" ){
                    var series = chart.series.push(am5xy.ColumnSeries.new(self.root, {
                        stacked: true,
                        name: `${ks_data[k].label}`,
                        xAxis: xAxis,
                        yAxis: yAxis,
                        valueXField:`${ks_data[k].label}`,
                        categoryYField: "category",
                        sequencedInterpolation: true,
                        tooltip: tooltip
                    }));

                } else if (ks_data[k].type != "line" && self.props.record.data.ks_dashboard_item_type == 'ks_horizontalBar_chart') {
                    var series = chart.series.push(am5xy.ColumnSeries.new(self.root, {
                        name: `${ks_data[k].label}`,
                        xAxis: xAxis,
                        yAxis: yAxis,
                        valueXField:`${ks_data[k].label}`,
                        categoryYField: "category",
                        sequencedInterpolation: true,
                        tooltip: tooltip

                    }));
                }
                    if (self.props.record.data.ks_show_records == true && series){
                        series.columns.template.setAll({
    //                        width: am5.percent(80-(10*k)),
                            height: am5.p100,
                            strokeOpacity: 0
                       });
                       var cursor = chart.set("cursor", am5xy.XYCursor.new(this.root, {
                                behavior: "zoomY"
                        }));
                       cursor.lineY.set("forceHidden", true);
                       cursor.lineX.set("forceHidden", true);
                    }
                    if (self.props.record.data.ks_show_data_value == true && series){
                        series.bullets.push(function () {
                            return am5.Bullet.new(self.root, {
    //                            locationX: 1,
                                    sprite: am5.Label.new(self.root, {
                                      text:  "{valueX}",
                                      fill: self.root.interfaceColors.get("alternativeText"),
                                      centerY: am5.p50,
                                      centerX: am5.p50,
                                      populateText: true
                                    })
                            });
                        });
                    }
                    if (series){
                      series.data.setAll(data);
                    }
               if (ks_data[k].type == "line" && self.props.record.data.ks_dashboard_item_type == 'ks_horizontalBar_chart' ){
                    var series2 = chart.series.push(
                        am5xy.LineSeries.new(self.root, {
                            name: `${ks_data[k].label}`,
                            xAxis: xAxis,
                            yAxis: yAxis,
                            valueXField:`${ks_data[k].label}`,
                            categoryYField: "category",
                            sequencedInterpolation: true,
                            tooltip: am5.Tooltip.new(self.root, {
                                pointerOrientation: "horizontal",
                                labelText: "{categoryY}, {name}: {valueX}"
                            })
                        })
                    );

                    series2.strokes.template.setAll({strokeWidth: 3,templateField: "strokeSettings"});
                    series2.bullets.push(function() {
                        return am5.Bullet.new(self.root, {
                            sprite: am5.Circle.new(self.root, {
                                strokeWidth: 3,
                                stroke: series2.get("stroke"),
                                radius: 5,
                                fill: self.root.interfaceColors.get("background")
                            })
                        });
                    });
                    series2.data.setAll(data);

                }

            }
            break;
            case "ks_line_chart":
            case "ks_area_chart":
                var chart = this.root.container.children.push(am5xy.XYChart.new(this.root, {panX: false,panY: false,
                wheelX: "panX",wheelY: "zoomX",layout: this.root.verticalLayout}));
                var xRenderer = am5xy.AxisRendererX.new(this.root, {
                minGridDistance: 15,
                minorGridEnabled: true
                });
                xRenderer.labels.template.setAll({
                  direction: "rtl",
                  rotation: -45,
                  centerY: am5.p50,
                  centerX: am5.p100,
                  paddingRight: 10
                });
                var xAxis = chart.xAxes.push(am5xy.CategoryAxis.new(this.root, {
                    categoryField: "category",
                    maxDeviation: 0.2,
                    renderer: xRenderer,
                    tooltip: am5.Tooltip.new(this.root, {})
                }));
                xAxis.data.setAll(data);

                var yAxis = chart.yAxes.push(am5xy.ValueAxis.new(this.root, {extraMin: 0,
                extraMax: 0.1,renderer: am5xy.AxisRendererY.new(this.root, {strokeOpacity: 0.1}) }));

                for (let k = 0;k<ks_data.length ; k++){
                    var tooltip = am5.Tooltip.new(this.root, {
                        textAlign: "center",
                        centerX: am5.percent(96),
                        labelText: "[bold]{categoryX}[/]\n{name}: {valueY}"
                    });

                    tooltip.label.setAll({
                        direction: "rtl"
                    })
                    var series = chart.series.push(am5xy.LineSeries.new(this.root, {
                        name: `${ks_data[k].label}`,
                        xAxis: xAxis,
                        yAxis: yAxis,
                        valueYField: `${ks_data[k].label}`,
                        categoryXField: "category",
                        alignLabels: true,
                        tooltip: tooltip
                    }));
                    series.strokes.template.setAll({strokeWidth: 2,templateField: "strokeSettings"});

                    series.bullets.push(function() {
                        var graphics = am5.Rectangle.new(self.root, {
                            width:7,
                            height:7,
                            centerX:am5.p50,
                            centerY:am5.p50,
                            fill: series.get("stroke"),
                        });

                        return am5.Bullet.new(self.root, {
                            sprite: graphics
                        });
                    });
                    if (self.props.record.data.ks_show_data_value == true && series){
                        series.bullets.push(function () {
                            return am5.Bullet.new(self.root, {
                                sprite: am5.Label.new(self.root, {
                                    text:  "{valueY}",
                                    centerX:am5.p50,
                                    centerY:am5.p100,
                                    populateText: true
                                 })
                            });
                        });
                    }
                    if (self.props.record.data.ks_dashboard_item_type === "ks_area_chart"){
                        series.fills.template.setAll({
                            fillOpacity: 0.5,
                            visible: true
                        });
                    }

                    series.data.setAll(data);
                }

                if (self.props.record.data.ks_show_records == true){
                    var cursor = chart.set("cursor", am5xy.XYCursor.new(this.root, {
                        behavior: "none"
                    }));
                    cursor.lineY.set("forceHidden", true);
                    cursor.lineX.set("forceHidden", true);

                }
                break;
                case "ks_pie_chart":
                case "ks_doughnut_chart":
                    var series = []
                    if (rec.ks_semi_circle_chart == true && (rec.ks_dashboard_item_type == "ks_pie_chart" ||rec.ks_dashboard_item_type == "ks_doughnut_chart")){
                         if (rec.ks_dashboard_item_type == 'ks_doughnut_chart'){
                            var chart = this.root.container.children.push(
                                am5percent.PieChart.new(this.root, {
                                   innerRadius : am5.percent(50),
                                   layout: this.root.verticalLayout,
                                   startAngle: 180,
                                   endAngle: 360,
                            }));
                        }else{
                            var chart = this.root.container.children.push(
                                am5percent.PieChart.new(this.root, {
                                    radius: am5.percent(100),
                                    layout: this.root.verticalLayout,
                                    startAngle: 180,
                                    endAngle: 360,
                                }));
                        }
                         var legend = chart.children.push(am5.Legend.new(this.root, {
                            centerX: am5.p50,
                            x: am5.p50,
                            marginTop: 15,
                            marginBottom: 15,
                            layout: this.root.horizontalLayout,
                           }));
                        for (let k = 0;k<ks_data.length ; k++){
                            series[k] = chart.series.push(
                                am5percent.PieSeries.new(this.root, {
                                name: `${ks_data[k].label}`,
                                valueField: `${ks_data[k].label}`,
                                categoryField: "category",
                                alignLabels: false,
                                startAngle: 180,
                                endAngle: 360,
                            }));
                        }
                    }else{
                        if (rec.ks_dashboard_item_type == "ks_doughnut_chart"){
                            var chart = this.root.container.children.push(
                                am5percent.PieChart.new(this.root, {
                                innerRadius: am5.percent(50),
                                layout: this.root.verticalLayout,
                            }));
                        }else{
                            var chart = this.root.container.children.push(
                                am5percent.PieChart.new(this.root, {
                                radius: am5.percent(100),
                                layout: this.root.verticalLayout,
                            }));
                        }

//                         this.root.rtl=true;
                         var legend = chart.children.push(am5.Legend.new(this.root, {
                            centerX: am5.p50,
                            x: am5.p50,
                            marginTop: 15,
                            marginBottom: 15,
                            layout: this.root.horizontalLayout,
                           }));


                        for (let k = 0;k<ks_data.length ; k++){
                            series[k] = chart.series.push(
                                am5percent.PieSeries.new(this.root, {
                                name: `${ks_data[k].label}`,
                                valueField: `${ks_data[k].label}`,
                                categoryField: "category",
                                alignLabels: false,
//                                direction: "rtl",
                            })
                            );
                        }
                    }
                    var bgColor = this.root.interfaceColors.get("background");
                    for (let item of series){
                        item.ticks.template.setAll({forceHidden:true})
                        item.slices.template.setAll({
                            stroke: bgColor,
                            strokeWidth: 2,
                            templateField: "settings",
                            });
                        if (self.props.record.data.ks_show_records == true){
                            var tooltip = am5.Tooltip.new(this.root, {
                                textAlign: "center",
                                centerX: am5.percent(96)
                            });
                            tooltip.label.setAll({
                                direction: "rtl"
                            })
                            item.slices.template.setAll({
                                tooltipText: "[bold]{category}[/]\n{name}: {value}",
                                tooltip: tooltip
                            });
                        }
                        if (self.props.record.data.ks_show_data_value == true){
                            item.labels.template.setAll({
                                text: self.props.record.data.ks_data_label_type == 'value'? "{value}":("{valuePercentTotal}%") ,
                                inside: true,
                                textType: data?.length>10? "radial" : "circular",
                                centerX: am5.percent(80)
                            })
                        }
                        else{
                            item.labels.template.setAll({forceHidden:true})
                        }
                        item.data.setAll(data)
                        if(self.props.record.data.ks_hide_legend == true && series){
                            legend.data.setAll(item.dataItems);
                        }

                        item.appear(1000, 100);
                    }
                    break;
                case "ks_polarArea_chart":
                case "ks_radar_view":
                case "ks_flower_view":
                case "ks_radialBar_chart":
                    var chart = this.root.container.children.push(am5radar.RadarChart.new(this.root, {
                        panX: false,
                        panY: false,
                        wheelX: "panX",
                        wheelY: "zoomX",
                        radius: am5.percent(80),
                        layout: this.root.verticalLayout,
                    }));
                    if (rec.ks_dashboard_item_type == "ks_flower_view"){
                        var xRenderer = am5radar.AxisRendererCircular.new(this.root, {});
                        xRenderer.labels.template.setAll({
                            radius: 10,
                            cellStartLocation: 0.2,
                            cellEndLocation: 0.8
                        });
                    }else if (rec.ks_dashboard_item_type == "ks_radialBar_chart"){
                        var xRenderer = am5radar.AxisRendererCircular.new(this.root, {
                            strokeOpacity: 0.1,
                            minGridDistance: 50
                         });
                        xRenderer.labels.template.setAll({
                            radius: 23,
                            maxPosition: 0.98
                        });
                    }else{
                         var xRenderer = am5radar.AxisRendererCircular.new(this.root, {});
                            xRenderer.labels.template.setAll({
                            radius: 10
                        });
                    }
                    if (rec.ks_dashboard_item_type == "ks_radialBar_chart"){
                        var xAxis = chart.xAxes.push(am5xy.ValueAxis.new(this.root, {
                            renderer: xRenderer,
                            extraMax: 0.1,
                            tooltip: am5.Tooltip.new(self.root, {})
                        }));

                        var yAxis = chart.yAxes.push(am5xy.CategoryAxis.new(this.root, {
                            categoryField: "category",
                            renderer: am5radar.AxisRendererRadial.new(self.root, { minGridDistance: 20 })
                        }));
                        yAxis.get("renderer").labels.template.setAll({
                            oversizedBehavior: "truncate",
                            textAlign: "center",
                            maxWidth: 150,
                            ellipsis: "..."
                        });
                    }else{
                        var xAxis = chart.xAxes.push(am5xy.CategoryAxis.new(self.root, {
                            maxDeviation: 0,
                            categoryField: "category",
                            renderer: xRenderer,
                            tooltip: am5.Tooltip.new(self.root, {})
                        }));
                        xAxis.data.setAll(data);

                        var yAxis = chart.yAxes.push(am5xy.ValueAxis.new(self.root, {
                            renderer: am5radar.AxisRendererRadial.new(self.root, {})
                        }));
                    }

                    if (rec.ks_dashboard_item_type == "ks_polarArea_chart"){
                        for (let k = 0;k<ks_data.length ; k++) {
                            var series = chart.series.push(am5radar.RadarColumnSeries.new(self.root, {
                            stacked: true,
                            name: `${ks_data[k].label}`,
                            xAxis: xAxis,
                            yAxis: yAxis,
                            valueYField: `${ks_data[k].label}`,
                            categoryXField: "category",
                            alignLabels: true,
                            }));

                        series.set("stroke", self.root.interfaceColors.get("background"));
                        if (rec.ks_show_records == true){
                            var tooltip = am5.Tooltip.new(this.root, {
                                textAlign: "center",
                                centerX: am5.percent(96)
                            });
                            tooltip.label.setAll({
                                direction: "rtl"
                            })

                            series.columns.template.setAll({
                                width: am5.p100,
                                strokeOpacity: 0.1,
                                tooltipText: "{name}: {valueY}",
                                tooltip: tooltip
                            });
                        }

                        series.data.setAll(data);
                        }
                    }else if (rec.ks_dashboard_item_type == "ks_flower_view"){
                        for (let k = 0;k<ks_data.length ; k++){
                            var series = chart.series.push(
                                am5radar.RadarColumnSeries.new(self.root, {
                                name: `${ks_data[k].label}`,
                                xAxis: xAxis,
                                yAxis: yAxis,
                                valueYField: `${ks_data[k].label}`,
                                categoryXField: "category"
                             })
                            );

                            var tooltip = am5.Tooltip.new(this.root, {
                                textAlign: "center",
                                centerX: am5.percent(96)
                            });
                            tooltip.label.setAll({
                                direction: "rtl"
                            })

                            series.columns.template.setAll({
                                tooltipText: "{name}: {valueY}",
                                width: am5.percent(100),
                                tooltip: tooltip
                            });
                            series.data.setAll(data);
                        }

                    }else if (rec.ks_dashboard_item_type == "ks_radialBar_chart"){
                        for (let k = 0;k<ks_data.length ; k++) {
                            var series = chart.series.push(am5radar.RadarColumnSeries.new(self.root, {
                                stacked: true,
                                name: `${ks_data[k].label}`,
                                xAxis: xAxis,
                                yAxis: yAxis,
                                valueXField: `${ks_data[k].label}`,
                                categoryYField: "category"
                            }));

                            series.set("stroke",self.root.interfaceColors.get("background"));
                            var tooltip = am5.Tooltip.new(this.root, {
                                textAlign: "center",
                                centerX: am5.percent(96)
                            });
                            tooltip.label.setAll({
                                direction: "rtl"
                            })
                            series.columns.template.setAll({
                                width: am5.p100,
                                strokeOpacity: 0.1,
                                tooltipText: "{name}: {valueX}  {category}",
                                tooltip: tooltip
                            });
                            series.data.setAll(data);
                        }
                        yAxis.data.setAll(data);
                   }
                    else{
                        for (let k = 0;k<ks_data.length ; k++){
                            var tooltip = am5.Tooltip.new(this.root, {
                                textAlign: "center",
                                centerX: am5.percent(96),
                                labelText: "{valueY}"
                            });
                            tooltip.label.setAll({
                                direction: "rtl"
                            })
                            var series = chart.series.push(am5radar.RadarLineSeries.new(self.root, {
                                name:`${ks_data[k].label}`,
                                xAxis: xAxis,
                                yAxis: yAxis,
                                valueYField: `${ks_data[k].label}`,
                                categoryXField: "category",
                                alignLabels: true,
                                tooltip: tooltip
                            }));

                            series.strokes.template.setAll({
                            strokeWidth: 2,

                            });

                        series.bullets.push(function () {
                            return am5.Bullet.new(self.root, {
                                sprite: am5.Circle.new(self.root, {
                                radius: 5,
                                fill: series.get("fill")
                            })
                             });
                        });
                        series.data.setAll(data);
                    }
                        }
                    xAxis.data.setAll(data);
                    break;

                case "ks_scatter_chart":
                var chart = this.root.container.children.push(am5xy.XYChart.new(this.root, {panX: false,panY: false,
                 wheelX: "panX",wheelY: "zoomX",layout: this.root.verticalLayout}));
                    var xAxis = chart.xAxes.push(am5xy.ValueAxis.new(self.root, {
                        renderer: am5xy.AxisRendererX.new(self.root, { minGridDistance: 50 }),
                        tooltip: am5.Tooltip.new(self.root, {})
                    }));
                    xAxis.ghostLabel.set("forceHidden", true);

                    var yAxis = chart.yAxes.push(am5xy.ValueAxis.new(self.root, {
                        renderer: am5xy.AxisRendererY.new(self.root, {}),
                        tooltip: am5.Tooltip.new(self.root, {})
                    }));
                    yAxis.ghostLabel.set("forceHidden", true);

                    for (let k = 0;k<ks_data.length ; k++){
                        var tooltip = am5.Tooltip.new(this.root, {
                            textAlign: "center",
                            centerX: am5.percent(96),
                            labelText: "{name_1}:{valueX} {name}:{valueY}"
                        });
                        tooltip.label.setAll({
                            direction: "rtl"
                        })

                        var series = chart.series.push(am5xy.LineSeries.new(self.root, {
                            name:`${ks_data[k].label}`,
                            name_1 : chart_data.groupby,
                            calculateAggregates: true,
                            xAxis: xAxis,
                            yAxis: yAxis,
                            valueYField: `${ks_data[k].label}`,
                            valueXField: "category",
                            tooltip: tooltip
                        }));

                        series.bullets.push(function() {
                            var graphics = am5.Triangle.new(self.root, {
                                fill: series.get("fill"),
                                width: 10,
                                height: 7
                            });
                            return am5.Bullet.new(self.root, {
                                sprite: graphics
                            });
                        });
                         var cursor = chart.set("cursor", am5xy.XYCursor.new(self.root, {
                            behavior: "none",
                            snapToSeries: [series]
                            }));
                            cursor.lineY.set("forceHidden", true);
                            cursor.lineX.set("forceHidden", true);
                        series.strokes.template.set("strokeOpacity", 0);
                        series.data.setAll(data);

                    }
                    break;
            }
             if (rec.ks_dashboard_item_type != 'ks_pie_chart' && rec.ks_dashboard_item_type != 'ks_doughnut_chart' )
                {
                 this.root.rtl=true;
                 var legend = chart.children.push(
                    am5.Legend.new(this.root, {
                        centerX: am5.p50,
                        x: am5.p50,
                        layout: self.root.gridLayout,
                        y: am5.percent(100),
                        centerY: am5.percent(100),
                    })
                );
                legend.labels.template.setAll({
                textAlign: "right",
                marginRight:5
                });
                legend.itemContainers.template.setAll({
                      reverseChildren: true
                    });
                if(self.props.record.data.ks_hide_legend == true && series){
                    legend.data.setAll(chart.series.values);
                }
                }


            if (rec.ks_data_format && rec.ks_data_format == 'global'){
                this.root.numberFormatter.setAll({
                    numberFormat: "#.0a",
                    bigNumberPrefixes: [{"number":1e+3,"suffix":"k"},{ "number": 1e+6, "suffix": "M" },
                    { "number": 1e+9, "suffix": "G" },{ "number": 1e+12, "suffix": "T" },
                    { "number": 1e+15, "suffix": "P" },{ "number": 1e+18, "suffix": "E" }]
                });
            }else if (rec.ks_data_format && rec.ks_data_format == 'indian'){
                this.root.numberFormatter.setAll({
                    numberFormat: "#.0a",
                    bigNumberPrefixes: [{"number":1e+3,"suffix":"Th"},{"number":1e+5,"suffix":"Lakh"},
                    { "number": 1e+7, "suffix": "Cr" },{ "number": 1e+9, "suffix": "Arab" }],
                });
            }else if (rec.ks_data_format && rec.ks_data_format == 'colombian'){
                this.root.numberFormatter.setAll({
                    numberFormat: "#.a",
                    bigNumberPrefixes: [{"number":1e+6,"suffix":"M"},{ "number": 1e+9, "suffix": "M" },{ "number": 1e+12, "suffix": "M" },
                    { "number": 1e+15, "suffix": "M" },{ "number": 1e+18, "suffix": "M" }]
                });
            }else{
                this.root.numberFormatter.setAll({
                    numberFormat: "#"
                });
            }

            chart.appear(1000, 100);
            if (rec.ks_dashboard_item_type != 'ks_pie_chart' &&  rec.ks_dashboard_item_type != 'ks_doughnut_chart' && series){
                series.appear();
            }
        }else{
            $(this.graphref.el).append($("<div class='graph_text'>").text("No Data Available."));
        }
        }else{
        $(this.graphref.el).append($("<div class='graph_text'>").text("No Data Available."));
        }

    }
}
KsGraphPreview.template = "Ksgraphview";
export const KsGraphPreviewfield = {
    component:KsGraphPreview,
    supportedTypes : ["char"]
};
registry.category("fields").add("ks_dashboard_graph_preview", KsGraphPreviewfield);